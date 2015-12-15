
import tempfile

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest
from django import forms
from django.shortcuts import render
from django.views.generic.list import ListView

import rest_framework.generics    as rest_generics
from rest_framework import serializers, status
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from wsrc.site.usermodel.models import Player
from wsrc.site.competitions.views import get_competition_lists
from wsrc.utils import xls_utils, sync_utils

JSON_RENDERER = JSONRenderer()

class MemberListView(ListView):

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            raise PermissionDenied()
        return super(MemberListView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
      return Player.objects.filter(user__is_active=True).order_by('user__first_name', 'user__last_name')

    def get_template_names(self):
      return ["memberlist.html"]

    def get_context_data(self, **kwargs):
        context = super(MemberListView, self).get_context_data(**kwargs)
        comp_lists = get_competition_lists()
        context.update(comp_lists)
        return context

class MyNullBooleanSelect(forms.widgets.Select):
    """
    A Select Widget intended to be used with NullBooleanField.
    """
    def __init__(self, attrs=None):
        choices = (('null', 'Unknown'),
                   ('true', 'Yes'),
                   ('false', 'No'))
        super(MyNullBooleanSelect, self).__init__(attrs, choices)

    def render(self, name, value, attrs=None, choices=()):
        try:
            value = {True: 'true', False: 'false'}[value]
        except KeyError:
            value = 'null'
        return super(MyNullBooleanSelect, self).render(name, value, attrs, choices)

    def value_from_datadict(self, data, files, name):
        value = data.get(name, None)
        return {'true': True,
                True: True,
                'True': True,
                'false': False,
                'False': False,
                False: False}.get(value, None)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'is_active')


class PlayerSerializer(serializers.ModelSerializer):
  user = UserSerializer()  
  class Meta:
    model = Player
    fields = ('id', 'user', 'cell_phone', 'other_phone', 'membership_type', 'wsrc_id', 'cardnumber', 'squashlevels_id', 'prefs_receive_email')
    depth = 1

class PlayerView(rest_generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,DjangoModelPermissions,)
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer

class UserView(rest_generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,DjangoModelPermissions,)
    queryset = User.objects.all()
    serializer_class = UserSerializer

class PlayerListView(rest_generics.ListCreateAPIView):
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,DjangoModelPermissions,)
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    def post(self, request, format="json"):
        player = request.DATA
        with transaction.atomic():
            user = player["user"]
            def get_and_remove(f):
                val = user[f]; del user[f]; return val
            username =  get_and_remove("username")
            password =  get_and_remove("password")
            email =     get_and_remove("email")
            is_active = get_and_remove("is_active")
            user_instance = User.objects.create_user(username, email, password, **user)
            user_instance.is_active = is_active
            user_instance.save()
            player["user"] = user_instance
            player_instance = Player.objects.create(**player)
            player_instance.save()
        return Response(status=status.HTTP_201_CREATED)

class UploadFileForm(forms.Form):
    file = forms.FileField(widget=forms.widgets.ClearableFileInput(attrs={'accept':'.csv,.xls'}))
    sheetname = forms.CharField(initial="masterfile")

class UserForm(forms.ModelForm):
    class Meta:
        model = User

class PlayerForm(forms.ModelForm):
    prefs_receive_email = forms.fields.NullBooleanField(widget=MyNullBooleanSelect)
    class Meta:
        model = Player

def admin_memberlist_view(request):
    if not request.user.is_authenticated() or request.user.groups.filter(name="Membership Editor").count() == 0:
        raise PermissionDenied()

    db_rows = Player.objects.order_by('user__last_name', 'user__first_name')
    ss_memberlist_rows = []
    upload_form = UploadFileForm()
    ss_vs_db_diffs = {}

    if request.method == 'POST':
        upload_form = UploadFileForm(request.POST, request.FILES)
        if upload_form.is_valid():
            upload = request.FILES['file']
            sheetname = request.POST['sheetname']
            if upload.name.endswith(".xls"):
                with tempfile.NamedTemporaryFile(suffix="xls") as fh:
                    for chunk in upload.chunks():
                        fh.write(chunk)
                    fh.flush()
                    ss_memberlist_rows= xls_utils.sheet_to_dict(fh.name, sheetname)
            elif upload.name.endswith(".csv"):
                reader = csv.DictReader(upload_generator(upload))
                ss_memberlist_rows = [row for row in reader]
            else:
                return HttpResponseBadRequest("<h1>Unknown file type</h1>")
            upload_form = None 
            mapping_array = sync_utils.find_matching(ss_memberlist_rows, db_rows, sync_utils.match_spreadsheet_with_db_record)
            assert(len(mapping_array) == len(ss_memberlist_rows))
            for i, db_row in enumerate(mapping_array):
                if db_row is not None:
                    ss_row = ss_memberlist_rows[i]
                    ss_row["db_id"] = db_row.id
                    diffs = sync_utils.compare_spreadsheet_with_db_record(ss_row, db_row)
                    if len(diffs) > 0:
                        ss_vs_db_diffs[db_row.id] = diffs
        

    db_rows_serialiser = PlayerSerializer(db_rows, many=True)
    db_rows_data = JSON_RENDERER.render(db_rows_serialiser.data)
    kwargs = {
        "upload_form":         upload_form,
        "db_members_data":     db_rows_data,
        "ss_members_data":     JSON_RENDERER.render(ss_memberlist_rows),
        "membership_types":    JSON_RENDERER.render(Player.MEMBERSHIP_TYPES),
        "ss_vs_db_diffs":      JSON_RENDERER.render(ss_vs_db_diffs),
        "new_user_form":       UserForm(auto_id='id_newuser_'),
        "new_member_form":     PlayerForm(auto_id='id_newmember_'),
        "change_user_form":    UserForm(auto_id='id_changeuser_'),
        "change_member_form":  PlayerForm(auto_id='id_changemember_'),
    }
    return render(request, "memberlist_admin.html", kwargs)
