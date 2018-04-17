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

import json
import logging
import operator
import tempfile
import urllib
import urllib2


from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.urlresolvers import reverse, reverse_lazy
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django import forms
from django.template.response import TemplateResponse
from django.shortcuts import render
from django.views.generic import DetailView
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView
from django.utils.decorators import method_decorator

import rest_framework.generics    as rest_generics
from rest_framework import serializers, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from wsrc.site.models import OAuthAccess
from wsrc.site.settings import settings
from wsrc.external_sites.booking_manager import BookingSystemSession
from wsrc.site.usermodel.models import Player, DoorCardEvent, MembershipApplication
from wsrc.utils import xls_utils, sync_utils, email_utils
from wsrc.utils.timezones import parse_iso_date_to_naive
from wsrc.utils.form_utils import add_formfield_attrs

from .activity_report import ActivityReport
from .forms import SettingsUserForm, SettingsPlayerForm, SettingsYoungPlayerForm, SettingsInfoForm, MembershipApplicationForm

JSON_RENDERER = JSONRenderer()
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


class SearchForm(forms.Form):
    search = forms.CharField()

class MemberListView(ListView):
    "Straightforward list view for active members"

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            raise PermissionDenied()
        return super(MemberListView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Player.objects.select_related("user")\
                                 .filter(user__is_active=True) \
                                 .exclude(prefs_display_contact_details=False) \
                                 .order_by('user__first_name', 'user__last_name')
        filter_text = self.request.GET.get("search")
        filter_ids = self.request.GET.get("filter-ids")
        if filter_text is not None:
            queryset = queryset.filter(Q(user__first_name__icontains=filter_text) |\
                                       Q(user__last_name__icontains=filter_text) |\
                                       Q(user__email__icontains=filter_text) |\
                                       Q(other_phone__icontains=filter_text) |\
                                       Q(cell_phone__icontains=filter_text))
        if filter_ids is not None:
            ids = filter_ids.split(",")
            clause = None
            for an_id in ids:
                aclause = Q(pk=an_id)
                clause = clause | aclause if clause is not None else aclause
            queryset = queryset.filter(clause)
                
        return queryset.values("id", "user__first_name", "user__last_name", "user__email",\
                                     "other_phone", "cell_phone", "user__is_active") \

    def get_template_names(self):
        return ["memberlist.html"]

    def get_context_data(self, **kwargs):
        ctx = super(MemberListView, self).get_context_data(**kwargs)
        form = SearchForm(data=self.request.GET)
        ctx["form"] = form
        return ctx


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

class DoorCardEventSerializer(serializers.ModelSerializer):
    "Simple REST serializer"
    class Meta:
        model = DoorCardEvent
        fields = ('id', 'card', 'event', 'timestamp')

class DoorCardEventCreateView(rest_generics.CreateAPIView):
    "REST view for entereing door card events"
    authentication_classes = (SessionAuthentication,)
    permission_classes = (IsAuthenticated, DjangoModelPermissions,)
    serializer_class = DoorCardEventSerializer
    model = DoorCardEvent
    queryset = DoorCardEvent.objects.all()

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

@login_required
def member_activity_view(request):
    if not request.user.is_staff:
        raise PermissionDenied()
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    if start_date is None or end_date is None:
        return HttpResponseBadRequest("missing start_date or end_date")
    try:
        start_date = parse_iso_date_to_naive(start_date)
        end_date = parse_iso_date_to_naive(end_date)
    except ValueError:
        return HttpResponseBadRequest("bad date format, should be YYYY-MM-DD")
    reporter = ActivityReport(start_date, end_date)
    if "djdt" in request.GET:
        # used for tracing SQL calls in the debug toolbar
        payload = "<html><body></body></html>"
        content_type = 'text/html'
    else:
        payload = reporter.create_report()
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response = HttpResponse(payload, content_type=content_type)
    if "djdt" not in request.GET:
        response['Content-Disposition'] = 'attachment; filename="activity_{start_date:%Y-%m-%d}_{end_date:%Y-%m-%d}.xlsx"'\
                                          .format(**locals())
    return response

@login_required
def settings_view(request):
    "Settings editor"
    success = False
    settings_form_cls = SettingsPlayerForm
    player = Player.get_player_for_user(request.user)
    subscription = player.get_current_subscription() if player is not None else None
    if subscription is not None and subscription.is_age_sensitive():
        settings_form_cls = SettingsYoungPlayerForm
    
    if request.method == 'POST':
        pform = settings_form_cls(request.POST, instance=player)
        uform = SettingsUserForm(request.POST, instance=request.user)
        if pform.is_valid() and uform.is_valid():
            with transaction.atomic():
                if pform.has_changed():
                    pform.save()
                if uform.has_changed():
                    uform.save()
                success = True
    else:
        pform = settings_form_cls(instance=player)
        uform = SettingsUserForm(instance=request.user)

    iform = SettingsInfoForm.create(player)
    add_formfield_attrs(pform)
    add_formfield_attrs(uform)
    add_formfield_attrs(iform)

    ctx = {
        'player_form':     pform,
        'user_form':       uform,
        'info_form':       iform,
        'form_saved':      success,
    }
    return TemplateResponse(request, 'settings.html', ctx)

class MembershipApplicationCreateView(CreateView):
    model = MembershipApplication
    template_name = "membership_application.html"
    success_url = reverse_lazy("membership_application_submitted")
    form_class = MembershipApplicationForm
    def __init__(self, *args, **kwargs):
        super(MembershipApplicationCreateView, self).__init__(*args, **kwargs)
        self.oauth_record = OAuthAccess.objects.get(name="reCAPTCHA")
    def get_form_kwargs(self):
        kwargs = super(MembershipApplicationCreateView, self).get_form_kwargs()
        kwargs["recaptcha_verifier"] = self.recaptcha_verifier
        return kwargs
    def get_context_data(self, **kwargs):
        context = super(MembershipApplicationCreateView, self).get_context_data(**kwargs)
        context["recaptcha_client_token"] = self.oauth_record.client_id
        return context
    def form_valid(self, form):
        response = super(MembershipApplicationCreateView, self).form_valid(form)
        self.send_verification_email()
        return response
    def recaptcha_verifier(self, token):
        LOGGER.debug("recaptcha token: %s", token)
        params = {
            "secret": self.oauth_record.client_secret,
            "response": token
        }
        url = self.oauth_record.auth_server_uri + self.oauth_record.token_endpoint
        request = urllib2.Request(url, urllib.urlencode(params))
        response = urllib2.urlopen(request)
        response = json.load(response)
        if not response.get("success"):
            LOGGER.warning("reCAPTCHA test failed, errors: %s", response.get("error-codes"))
            raise ValidationError("reCAPTCHA test failed. Please try again.", code='invalid')
    def send_verification_email(self):
        params = {"application": self.object}
        (text_body, html_body) = email_utils.get_email_bodies("Membership App. Verify Email", params)
        subject = "Woking Squash Club Membership Application"
        from_address = "membership@wokingsquashclub.org"
        to_list = [self.object.email]
        email_utils.send_email(subject, text_body, html_body, from_address, to_list)

class MembershipApplicationVerifiedEmailView(DetailView):
    model = MembershipApplication
    template_name = "membership_email_verified.html"
    
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        token = request.GET.get("token")
        if self.object.guid != token:
            return HttpResponseRedirect(reverse("membership_application_verify_email_failed"))
        self.object.email_verified = True
        self.object.save()
        return self.render_to_response(context)
