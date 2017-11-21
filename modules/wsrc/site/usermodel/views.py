# This file is part of WSRC.
#
# WSRC is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# WSRC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with WSRC.  If not, see <http://www.gnu.org/licenses/>.

"Views for users app, including a basic admin view"

import tempfile
import operator

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseBadRequest
from django import forms
from django.shortcuts import render
from django.views.generic.list import ListView

import rest_framework.generics    as rest_generics
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from wsrc.site.models import EventFilter
from wsrc.site.settings import settings
from wsrc.external_sites.booking_manager import BookingSystemSession
from wsrc.site.usermodel.models import Player
from wsrc.utils import xls_utils, sync_utils

from .forms import SettingsUserForm, SettingsPlayerForm, SettingsInfoForm, \
    create_notifier_filter_formset_factory

JSON_RENDERER = JSONRenderer()

class MemberListView(ListView):
    "Straightforward list view for active members"
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            raise PermissionDenied()
        return super(MemberListView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Player.objects.values("id", "user__first_name", "user__last_name", "user__email",\
                                     "other_phone", "cell_phone", "user__is_active") \
                             .filter(user__is_active=True) \
                             .exclude(prefs_display_contact_details=False) \
                             .order_by('user__first_name', 'user__last_name')

    def get_template_names(self):
        return ["memberlist.html"]

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
    "Simple REST serializer"
    date_joined = serializers.DateTimeField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name', 'email', 'is_active', 'date_joined')


class PlayerSerializer(serializers.ModelSerializer):
    "Simple REST serializer, includes foreignkey User"
    user = UserSerializer()
    ordered_name = serializers.CharField(source="get_ordered_name")
    cardnumber = serializers.CharField(source="get_cardnumbers")
    class Meta:
        "Class meta information"
        model = Player
        fields = ('id', 'ordered_name', 'user', 'cell_phone', 'other_phone', 'wsrc_id', 'booking_system_id',\
                  'cardnumber', 'squashlevels_id', 'prefs_receive_email')
        depth = 1

class PlayerView(rest_generics.RetrieveUpdateDestroyAPIView):
    "REST view"
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated, DjangoModelPermissions,)
    queryset = Player.objects.all().select_related("user")
    serializer_class = PlayerSerializer

class UserView(rest_generics.RetrieveUpdateDestroyAPIView):
    "REST view"
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated, DjangoModelPermissions,)
    queryset = User.objects.all()
    serializer_class = UserSerializer

class PlayerListView(rest_generics.ListCreateAPIView):
    "REST view of all players"
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated, DjangoModelPermissions,)
    queryset = Player.objects.all().select_related("user").prefetch_related("doorcards")
    serializer_class = PlayerSerializer
    def post(self, request, format="json"):
        player = request.data
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
    "Form accepting spreadsheet uploads"
    file = forms.FileField(widget=forms.widgets.ClearableFileInput(attrs={'accept':'.csv,.xls'}))
    sheetname = forms.CharField(initial="masterfile")

class BookingSystemCredentialsForm(forms.Form):
    "Form for obtaining creditials to access the booking system"
    username = forms.CharField()
    password = forms.CharField(widget=forms.widgets.PasswordInput)

class UserForm(forms.ModelForm):
    "Form for details stored on the User object"
    is_active = forms.fields.BooleanField(widget=MyNullBooleanSelect)
    class Meta:
        model = User
        fields = ('id', 'username', 'password', 'first_name', 'last_name', 'email', 'is_active', 'date_joined')

class PlayerForm(forms.ModelForm):
    "Form for player details - contact details and other preferences"
    prefs_receive_email = forms.fields.NullBooleanField(widget=MyNullBooleanSelect)
    class Meta:
        model = Player
        fields = ('id', 'user', 'cell_phone', 'other_phone', 'wsrc_id',\
                  'booking_system_id', 'squashlevels_id', 'prefs_receive_email')

class BookingSystemMemberView(APIView):
    "REST methods for an individual user of the booking system"
    def delete(self, request, bs_id): #pylint: disable=no-self-use
        "Permanently delete an id from the booking system"
        if request.user.groups.filter(name="Membership Editor").count() == 0 \
           and not request.user.is_superuser:
            raise PermissionDenied()
        credentials = settings.BOOKING_SYSTEM_CREDENTIALS
        username = credentials["username"]
        password = credentials["password"]
        booking_session = BookingSystemSession(username, password)
        booking_session.delete_user_from_booking_system(bs_id)
        return Response()
    def post(self, request): #pylint: disable=no-self-use
        "Create a new user on the booking system"
        if request.user.groups.filter(name="Membership Editor").count() == 0 \
           and not request.user.is_superuser:
            raise PermissionDenied()
        credentials = settings.BOOKING_SYSTEM_CREDENTIALS
        username = credentials["username"]
        password = credentials["password"]
        booking_session = BookingSystemSession(username, password)
        name = request.data["name"]
        pwd = request.data["password"]
        email = request.data.get("email")
        response = booking_session.add_user_to_booking_system(name, pwd, email)
        return Response(response)


class BookingSystemMembersView(APIView):
    "REST view of data obtained from the booking system"
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated,)
    parser_classes = (JSONParser,)
    def post(self, request, format="json"):
        if request.user.groups.filter(name="Membership Editor").count() == 0 \
           and not request.user.is_superuser:
            raise PermissionDenied()
        credentials = request.data
        username = credentials["username"]
        password = credentials["password"]
        booking_session = BookingSystemSession(username, password)
        bs_contacts = booking_session.get_memberlist()
        for row in bs_contacts:
            for field, value in row.items():
                value = row[field] = str(value)
                if field == 'name':
                    (first, last) = sync_utils.split_first_and_last_names(value)
                    row["first_name"] = first
                    row["last_name"] = last
        bs_contacts = [c for c in bs_contacts if c.get("name")]
        bs_contacts.sort(key=operator.itemgetter("last_name", "first_name"))
        bs_vs_db_diffs = sync_utils.get_differences_bs_vs_db(bs_contacts, Player.objects.filter(user__is_active=True).select_related())
        return Response({"contacts": bs_contacts, "diffs": bs_vs_db_diffs})

def admin_memberlist_view(request):
    if not request.user.is_authenticated() \
       or (request.user.groups.filter(name="Membership Editor").count() == 0
           and not request.user.is_superuser):
        raise PermissionDenied()

    db_rows = Player.objects.order_by('user__last_name', 'user__first_name').select_related("user").prefetch_related("doorcards")
    ss_memberlist_rows = []
    upload_form = UploadFileForm()
    ss_vs_db_diffs = {}

    if request.method == 'POST':
        upload_form = UploadFileForm(request.POST, request.FILES)
        if upload_form.is_valid():
            upload = request.FILES['file']
            sheetname = request.POST['sheetname']
            if upload.name.endswith(".xls"):
                with tempfile.NamedTemporaryFile(suffix="xls") as temp_fh:
                    for chunk in upload.chunks():
                        temp_fh.write(chunk)
                    temp_fh.flush()
                    ss_memberlist_rows = xls_utils.sheet_to_dict(temp_fh.name, sheetname)
#            elif upload.name.endswith(".csv"):
#                reader = csv.DictReader(upload_generator(upload))
#                ss_memberlist_rows = [row for row in reader]
            else:
                return HttpResponseBadRequest("<h1>Unknown file type</h1>")
            upload_form = None
            ss_vs_db_diffs = sync_utils.get_differences_ss_vs_db(ss_memberlist_rows, db_rows)


    db_rows_serialiser = PlayerSerializer(db_rows, many=True)
    db_rows_data = JSON_RENDERER.render(db_rows_serialiser.data)
    kwargs = {
        "upload_form":         upload_form,
        "db_members_data":     db_rows_data,
        "ss_members_data":     JSON_RENDERER.render(ss_memberlist_rows),
        "ss_vs_db_diffs":      JSON_RENDERER.render(ss_vs_db_diffs),
        "new_user_form":       UserForm(auto_id='id_newuser_'),
        "new_member_form":     PlayerForm(auto_id='id_newmember_'),
        "change_user_form":    UserForm(auto_id='id_changeuser_'),
        "change_member_form":  PlayerForm(auto_id='id_changemember_'),
        "booking_credentials_form":  BookingSystemCredentialsForm(),
    }
    return render(request, "memberlist_admin.html", kwargs)



@login_required
def settings_view(request):
    "Settings editor"
    max_filters = 7
    success = False
    player = Player.get_player_for_user(request.user)
    events = EventFilter.objects.filter(player=player)
    filter_formset_factory = create_notifier_filter_formset_factory(max_filters)
    initial = [{'player': player}] * (max_filters)
    if request.method == 'POST':
        pform = SettingsPlayerForm(request.POST, instance=player)
        uform = SettingsUserForm(request.POST, instance=request.user)
        eformset = filter_formset_factory(request.POST, queryset=events, initial=initial)
        if pform.is_valid() and uform.is_valid() and eformset.is_valid():
            with transaction.atomic():
                if pform.has_changed():
                    pform.save()
                if uform.has_changed():
                    uform.save()
                for form in eformset:
                    if form.has_changed():
                        if form.cleaned_data['player'] != player:
                            raise PermissionDenied()
                if eformset.has_changed():
                    eformset.save()
                    events = EventFilter.objects.filter(player=player)
                    eformset = filter_formset_factory(queryset=events, initial=initial)
                success = True
    else:
        pform = SettingsPlayerForm(instance=player)
        uform = SettingsUserForm(instance=request.user)
        eformset = filter_formset_factory(queryset=events, initial=initial)

    iform = SettingsInfoForm(instance=player)

    return render(request, 'settings.html', {
        'player_form':     pform,
        'user_form':       uform,
        'info_form':       iform,
        'notify_formset':  eformset,
        'n_notifiers':     len(events),
        'form_saved':      success,
    })
