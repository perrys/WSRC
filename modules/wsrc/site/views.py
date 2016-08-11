# -*- coding: utf-8 -*-
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

import sys

from wsrc.site.models import PageContent, SquashLevels, LeagueMasterFixtures, BookingSystemEvent, EventFilter, MaintenanceIssue, Suggestion, EmailContent, ClubEvent
from wsrc.site.competitions.models import CompetitionGroup
from wsrc.site.usermodel.models import Player
import wsrc.site.settings.settings as settings
from wsrc.utils import timezones, email_utils

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.forms.widgets import Select, CheckboxSelectMultiple, HiddenInput, Textarea
from django.forms.models import modelformset_factory
from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse as reverse_url
from django.db import transaction
from django.forms import ModelForm, TextInput
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.template import Template, Context
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_safe
from django.db.models import Q

import rest_framework.generics as rest_generics
from rest_framework.renderers import JSONRenderer
from rest_framework import serializers
from rest_framework.parsers import JSONParser
from rest_framework.views import APIView
from rest_framework.utils.serializer_helpers import ReturnDict

import collections
import markdown
import datetime
import urllib
import httplib
import httplib2
import json
import logging
import time
import base64
import os.path


FACEBOOK_GRAPH_URL              = "https://graph.facebook.com/"
FACEBOOK_GRAPH_ACCESS_TOKEN_URL = FACEBOOK_GRAPH_URL + "oauth/access_token"

WSRC_FACEBOOK_PAGE_ID = 576441019131008
COURT_SLOT_LENGTH = datetime.timedelta(minutes=45)

COMMITTEE_EMAIL_ADDRESS = "committee@wokingsquashclub.org"
MAINT_OFFICER_EMAIL_ADRESS = "maintenance@wokingsquashclub.org"

HOME_TEAM_SHORT_NAMES = {
    u"Woking 1": "1sts",
    u"Woking 2": "2nds",
    u"Woking 3": "3rds",
    u"Woking 4": "4ths",
    }
        
AWAY_TEAM_SHORT_NAMES = {
    "Racquets": "R.",
    "Nuffield": "Nuf'ld",
    "Cannons": "Can's",
    "David Lloyd": "D. Lloyd",
    "Virgin Active": "V. Active",
    "Tennis & Squash": "T. & S.",
    "Surrey Sports Park": "Surrey S. P.",
    }        

JSON_RENDERER = JSONRenderer()
LW_REQUEST = collections.namedtuple('LW_REQUEST', ['query_params'])

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.WARNING)

def get_pagecontent_ctx(page):
    data = get_object_or_404(PageContent, page__iexact=page)
    result = {
        "pagedata": {
            "title": data.page,
            "content": markdown.markdown(data.markup),
            "last_updated": data.last_updated,
            },
        }
    return result

@require_safe
def generic_view(request, page):
    "Informational views rendered directly from markdown content stored in the DB"
    ctx = get_pagecontent_ctx(page)
    return TemplateResponse(request, 'generic_page.html', ctx)


def generate_tokens(date):
    start_times = {
        1: datetime.datetime.combine(date, datetime.time(8, 30)),
        2: datetime.datetime.combine(date, datetime.time(8, 45)),
        3: datetime.datetime.combine(date, datetime.time(9)),
    }
    court_length = datetime.timedelta(minutes=45)
    def times(court, start):
        m = {}
        while (start.time().hour < 23):
            m[start.time().strftime("%H:%M")] = BookingSystemEvent.generate_hmac_token(start, court)
            start += court_length
        return m
    return dict([(court, times(court, start)) for court, start in start_times.items()]) 
    

@require_safe
def index_view(request):

    ctx = get_pagecontent_ctx('home')
    levels = SquashLevels.objects.all().order_by('-level')
    if len(levels) > 0:
        ctx["squashlevels"] = levels

    leaguemasterfixtures = LeagueMasterFixtures.objects.all().order_by('date')
    rich_fixtures = []
    found_empty = False
    for idx,f in enumerate(leaguemasterfixtures):
        opponents = f.opponents
        for k,v in AWAY_TEAM_SHORT_NAMES.iteritems():
            opponents = opponents.replace(k,v)
        d = {
            "date": f.date,
            "team": HOME_TEAM_SHORT_NAMES[f.team],
            "opponents": opponents,
            "home_or_away": f.home_or_away,
            "scores": None,
            "points": None,
            "url": f.url,
            }
        if f.team1_score is not None:
            found_empty = False
            d["scores"] = "%d&#8209;%d" % (f.team1_score, f.team2_score)
            d["points"] = "%d&#8209;%d" % (f.team1_points, f.team2_points)
            if f.team1_points > f.team2_points:
                d["class"] = "won"
            elif f.team1_points < f.team2_points:
                d["class"] = "lost"
        elif not found_empty:
            found_empty = True
            ctx["leaguemaster_last_result_idx"] = idx
            ctx["leaguemaster_recent_min_idx"] = idx-5
            ctx["leaguemaster_recent_max_idx"] = idx+4
        rich_fixtures.append(d)
    ctx["leaguemaster"] = rich_fixtures
    if not found_empty:
        last = len(leaguemasterfixtures)-1
        ctx["leaguemaster_last_result_idx"] = last
        ctx["leaguemaster_recent_min_idx"] = last-9
        ctx["leaguemaster_recent_max_idx"] = last
        

    now = timezone.now()
    today_str = timezones.as_iso_date(now)
    midnight_today = now - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds = now.microsecond)
    cutoff_today = midnight_today + datetime.timedelta(hours=7)
    midnight_tomorrow = midnight_today + datetime.timedelta(days=1)
    bookings = BookingSystemEvent.objects.filter(start_time__gte=cutoff_today, start_time__lt=midnight_tomorrow).order_by('start_time')

    fake_context = {"request": LW_REQUEST({"date": today_str})}
    bookings_data = BookingSerializer(bookings, many=True, context=fake_context).data
    
    ctx["bookings"] = JSON_RENDERER.render(bookings_data)
    ctx["today"] = today_str
    return TemplateResponse(request, 'index.html', ctx)
        
    
@require_safe
def facebook_view(request):
    "Proxy view for the FB graph data from the WSRC page feed"

    def FBException(Exception):
        def __init__(self, message, errortype, statuscode):
            super(FBException, self).__init__(message)
            self.statuscode = statuscode
            self.errortype = type

    def fb_get(url):
      h = httplib2.Http()
      (resp_headers, content) = h.request(url, "GET")
      if resp_headers.status != httplib.OK:
          LOGGER.error("unable to fetch FB data, status = " + str(resp_headers.status) + ", response: " +  content)
          if len(content) > 0:
              try:
                  response = json.loads(content)
                  error = response.get("error")
                  if error is not None:
                      raise FBException(error["message"], error["errortype"], error["code"])
              except:
                  pass
          raise FBException(content, resp_headers.reason, resp_headers.status)
      return content
    
    def obtain_auth_token():
      LOGGER.info("Refreshing Facebook access token...")
      params = {
          "grant_type":    "client_credentials",
          "client_id" :    settings.FB_APP_ID,
          "client_secret": settings.FB_APP_SECRET,
          }
      url = FACEBOOK_GRAPH_ACCESS_TOKEN_URL +  "?" + urllib.urlencode(params)
      return fb_get(url)

    # First get an access token (using a pre-configured app ID) then use that to get the page feed
    token = obtain_auth_token()
    url = FACEBOOK_GRAPH_URL + str(WSRC_FACEBOOK_PAGE_ID) + "/feed?" + token
    try:
        # the response is JSON so pass it straight through
        return HttpResponse(fb_get(url), content_type="application/json")
    except FBException, e:
        msg = "ERROR: Unable to fetch Facebook page: %s [%d] - %s" % [e.reason, e.statuscode, e.message]
        return HttpResponse(content=msg,
                            content_type="text/plain", 
                            status=httplib.SERVICE_UNAVAILABLE)
    
@login_required
def change_password_view(request):

    success = False
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            success = True
        return redirect(reverse_url(settings_view))
    else:
        form = PasswordChangeForm(user=request.user)

    ctx = {"set_password_form": form}
    return TemplateResponse(request, 'change_password.html', ctx)

@login_required
def logout_dialog_view(request):
    return TemplateResponse(request, 'logout.html')
    

@login_required
def admin_mailshot_view(request):
    if not request.user.is_staff:
        raise PermissionDenied()
    from_email_addresses = ["chairman", 
                            "clubnight", 
                            "coach", 
                            "committee", 
                            "development",
                            "juniors", 
                            "leagues", 
                            "maintenance", 
                            "membership", 
                            "secretary", 
                            "social", 
                            "tournaments", 
                            "treasurer", 
                            "webmaster"]
    def get_comp_entrants(*group_types):
        clause = None
        for group_type in group_types:
            q = Q(comp_type=group_type)
            if clause is None:
                clause = q
            else:
                clause |= q
        groups = CompetitionGroup.objects.filter(clause).filter(active=True).all()
        player_ids = set()
        for group in groups:
          for comp in group.competition_set.all():
            for entrants in comp.entrant_set.all():
                player_ids.add(entrants.player1.id)
                if entrants.player2 is not None:
                    player_ids.add(entrants.player2.id)
        return player_ids
    ctx = {
        "players": Player.objects.filter(user__is_active=True),
        "from_email_addresses": [x + "@wokingsquashclub.org" for x in from_email_addresses],
        "membership_types": Player.MEMBERSHIP_TYPES,
        "tournament_player_ids": get_comp_entrants("wsrc_tournaments", "wsrc_qualifiers"),
        "box_player_ids": get_comp_entrants("wsrc_boxes"),
        }
    return TemplateResponse(request, 'mailshot.html', ctx)

class SendEmail(APIView):
    parser_classes = (JSONParser,)
    def put(self, request, format="json"):
        if not request.user.is_authenticated() or not request.user.is_staff:
            raise PermissionDenied()
        email_data = request.data
        fmt  = email_data.pop('format')
        body = email_data.pop('body')
        if fmt == 'mixed':
            email_data['text_body'] = body
            email_data['html_body'] = markdown.markdown(body)
        elif fmt == 'text':
            email_data['text_body'] = body
            email_data['html_body'] = None
        elif fmt == 'html':
            email_data['text_body'] = ''
            email_data['html_body'] = body
        debug = False
        if debug:
          import pprint, time
          print pprint.pprint(email_data)
          time.sleep(1)
          if 'stewart.c.perry@gmail.com' in email_data['bcc_list']:
              return HttpResponse("Invalid email address", content_type="text/plain", status=403)
        else:
          import wsrc.utils.email_utils as email_utils
          email_utils.send_email(**email_data)
        return HttpResponse(status=204)

class UserForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields["first_name"].label = "First Name"
        self.fields["last_name"].label = "Last Name"
        self.fields["email"].label = "Email"
    class Meta:
        model = User
        fields = ["first_name", "last_name", "username",  "email"]

class PlayerForm(ModelForm):
    class Meta:
        model = Player
        fields = ["cell_phone", "other_phone", "short_name", "prefs_receive_email"]
        exclude = ('user',)
 
def create_notifier_filter_formset_factory(max_number):
    time_choices = [
        ("", "Please Select"),
        ("08:00:00", "8am"),
        ("10:00:00", "10am"),
        ("12:00:00", "12pm"),
        ("14:00:00", "2pm"),
        ("16:00:00", "4pm"),
        ("17:00:00", "5pm"),
        ("18:00:00", "6pm"),
        ("18:30:00", "6:30pm"),
        ("19:00:00", "7pm"),
        ("19:30:00", "7:30pm"),
        ("20:00:00", "8pm"),
        ("21:00:00", "9pm"),
        ("22:00:00", "10pm"),
                ]
    notice_period_choices = [
        ("", "Please Select"),
        (30, "30 minutes"),
        (60, "1 hour"),
        (120, "2 hours"),
        (180, "3 hours"),
        (240, "4 hours"),
        (300, "5 hours"),
        (360, "6 hours"),
        (720, "12 hours"),
        (1440, "1 day"),
        ]
    return modelformset_factory(
        EventFilter, 
        can_delete = True,
        extra=max_number,
        max_num=max_number,
        fields = ["earliest", "latest", "notice_period_minutes", "days", "player"],
        widgets = {
            "earliest": Select(choices=time_choices),
            "latest": Select(choices=time_choices),
            "notice_period_minutes": Select(choices=notice_period_choices),
            "days": CheckboxSelectMultiple(),
            "player": HiddenInput(),
        }
    )

class InfoForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(InfoForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            for field in ["cardnumber", "squashlevels_id", "wsrc_id"]:
                self.fields[field].widget.attrs['readonly'] = "readonly"
                self.fields[field].widget.attrs['disabled'] = "disabled"
            self.fields['membership_type'].widget.attrs['disabled'] = "disabled"
    
    class Meta:
        model = Player
        fields = ["membership_type",  "wsrc_id", "cardnumber",  "squashlevels_id"]
        exclude = ('user',)

@login_required
def settings_view(request):

    max_filters = 7
    success = False
    player = request.user.player
    events = EventFilter.objects.filter(player=player)
    filter_formset_factory = create_notifier_filter_formset_factory(max_filters)
    initial = [{'player': player}] * (max_filters)
    if request.method == 'POST': 
        pform = PlayerForm(request.POST, instance=request.user.player)
        uform = UserForm(request.POST, instance=request.user)
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
        pform = PlayerForm(instance=request.user.player)
        uform = UserForm(instance=request.user)
        eformset = filter_formset_factory(queryset=events, initial=initial)

    iform = InfoForm(instance=request.user.player)

    return render(request, 'settings.html', {
        'player_form':     pform,
        'user_form':       uform,
        'info_form':       iform,
        'notify_formset':  eformset,
        'n_notifiers':     len(events),
        'form_saved':      success,
    })

class MaintenanceForm(ModelForm):
    class Meta:
        model = MaintenanceIssue
        fields = ["description"]
        widgets = {
            "description": Textarea(attrs={"rows": "3"})
        }

class SuggestionForm(ModelForm):
    class Meta:
        model = Suggestion
        fields = ["description"]
        widgets = {
            "description": Textarea(attrs={"rows": "6"})
        }

def notify(template_name, kwargs, subject, to_list, cc_list, from_address):
    template_obj = EmailContent.objects.get(name=template_name)
    email_template = Template(template_obj.markup)
    context = Context(kwargs)
    context["content_type"] = "text/html"
    html_body = markdown.markdown(email_template.render(context))
    context["content_type"] = "text/plain"
    text_body = email_template.render(context)
    email_utils.send_email(subject, text_body, html_body, from_address, to_list, cc_list=cc_list)

@login_required
def maintenance_view(request):
    if request.method == 'POST': 
        form = MaintenanceForm(request.POST)
        if form.is_valid(): # if the form is invalid (i.e. empty) just do nothing
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.reporter = request.user.player
                instance.save()
                context = {"issue": instance}
                to_list = [request.user.email, MAINT_OFFICER_EMAIL_ADRESS]
                cc_list = [COMMITTEE_EMAIL_ADDRESS]
                notify("MaintenanceIssueReceipt", context, 
                       subject="WSRC Maintenance", to_list=to_list,
                       cc_list=cc_list, from_address=MAINT_OFFICER_EMAIL_ADRESS)
    form = MaintenanceForm()

    issues = [issue for issue in MaintenanceIssue.objects.all().order_by('-reported_date')]
    cmp_map = {'ar': 1, 'aa': 2, 'ni': 3, 'c': 3}
    def status_cmp(x, y):
        return cmp(cmp_map[x.status], cmp_map[y.status])
    issues.sort(status_cmp)

    kwargs = {
        'data': issues,
        'form': form
    }
    return render(request, "maintenance.html", kwargs)

@login_required
def suggestions_view(request):
    if request.method == 'POST': 
        form = SuggestionForm(request.POST)
        if form.is_valid(): # if the form is invalid (i.e. empty) just do nothing
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.suggester = request.user.player
                instance.save()
                email_target = COMMITTEE_EMAIL_ADDRESS
                context = {"suggestion": instance}
                to_list = [request.user.email, email_target]
                notify("SuggestionReceipt", context, 
                       subject="WSRC New Suggestion", to_list=to_list,
                       cc_list=None, from_address=COMMITTEE_EMAIL_ADDRESS)

    suggestions = Suggestion.objects.all().order_by('-submitted_date')
    form = SuggestionForm()
    kwargs = {
        'data': suggestions,
        'form': form
    }
    return render(request, 'suggestions.html', kwargs)


class DateTimeTzAwareField(serializers.DateTimeField):
    def to_representation(self, value):
        value = timezone.localtime(value) # convert UTC value in DB to local time
        return super(DateTimeTzAwareField, self).to_representation(value)


class CustomBookingListSerializer(serializers.ListSerializer):
    """Custom ListSerializer, which is automagically returneded by the
       BookingSerializer constructor when many=True argument is
       provided. Returns the list as an attribute of an object with
       some extra attributes for date and HMAC tokens"""

    def __init__(self, *args, **kwargs):
        ctx = kwargs.get('context')
        req = ctx is not None and ctx.get('request') or None
        super(CustomBookingListSerializer, self).__init__(*args, **kwargs)
        self.date = None
        if req is not None:
            date = req.query_params.get('date', None)
            if date is not None:
                self.date = timezones.parse_iso_date_to_naive(date)
                delta = req.query_params.get('day_offset', None)
                if delta is not None:
                    self.date += datetime.timedelta(days=int(delta))

    def to_representation(self, data):
      obj = super(CustomBookingListSerializer, self).to_representation(data)
      result = dict()
      result["bookings"] =  obj
      if self.date is not None:
          result["date"] = self.date.isoformat()
          dt = self.date - datetime.date.today()
          if dt.days >=0 and dt.days < 8:
              result["tokens"] = generate_tokens(self.date)
      return result

    # need to override as ListSerializer tries to return the contents
    # in a ReturnList
    @property
    def data(self):
        ret = super(serializers.ListSerializer, self).data
        return ReturnDict(ret, serializer=self)

class BookingSerializer(serializers.ModelSerializer):
    start_time = DateTimeTzAwareField()
    end_time   = DateTimeTzAwareField()
    class Meta:
      model = BookingSystemEvent
    @classmethod
    def many_init(cls, *args, **kwargs):
        kwargs['child'] = cls()
        return CustomBookingListSerializer(*args, **kwargs)

class BookingList(rest_generics.ListAPIView):
    serializer_class = BookingSerializer
    def get_queryset(self):
        queryset = BookingSystemEvent.objects.order_by("start_time")
        date = self.request.query_params.get('date', None)
        if date is not None:
            date = timezones.parse_iso_date_to_naive(date)
            date = datetime.datetime.combine(date, datetime.time(0, tzinfo=timezone.get_default_timezone()))
            delta = self.request.query_params.get('day_offset', None)
            if delta is not None:
              date = date + datetime.timedelta(days=int(delta))
            tplus1 = date + datetime.timedelta(days=1)
            queryset = queryset.filter(start_time__gte=date, start_time__lt=tplus1)
        return queryset

def auth_view(request):
    if request.method == 'GET': 
      data = {
          "username": request.user and request.user.username or None,

    "csrf_token": get_token(request)
      }
      return HttpResponse(json.dumps(data), content_type="application/json")
    elif request.method == 'POST': 
        from django.contrib.auth import authenticate, login
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                data = {
                    "username": request.user and request.user.username or None,
                    "csrf_token": get_token(request)
                }
                json_data = json.dumps(data)
                return HttpResponse(json.dumps(data), content_type="application/json", status=httplib.OK)
            else:
                return HttpResponse("inactive login", content_type="text/plain", status=httplib.FORBIDDEN)
        else:
            return HttpResponse("invalid login", content_type="text/plain", status=httplib.FORBIDDEN)
    elif request.method == 'DELETE': 
        logout(request)
        return HttpResponse(None, content_type="application/json", status=httplib.OK)
        

class MarkdownField(serializers.Field):
    def to_representation(self, value):
        return markdown.markdown(value)

class PictureField(serializers.Field):
    def to_representation(self, value):
        if not value or value.name is None:
            return None

        data = value.file.read()
        result = {
            "name": os.path.split(value.name)[1],
            "size": value.size,
            "width": value.width,
            "height": value.height,
            "data": base64.standard_b64encode(data),
        }
        return result

class ClubEventSerializer(serializers.ModelSerializer):
    markup   = MarkdownField()
    picture  = PictureField()
    class Meta:
        model = ClubEvent
        fields = ('title', 'display_date', 'display_time', 'markup', 'picture', 'last_updated')

class ClubEventList(rest_generics.ListAPIView):
    serializer_class = ClubEventSerializer
    def get_queryset(self):
        queryset = ClubEvent.objects.order_by("last_updated")
        return queryset.filter(Q(display_date__isnull=True) | Q(display_date__gte=datetime.date.today()))
