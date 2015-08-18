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

from wsrc.site.models import PageContent, SquashLevels, LeagueMasterFixtures, BookingSystemEvent, EventFilter
from wsrc.site.competitions.models import CompetitionGroup
from wsrc.site.usermodel.models import Player
import wsrc.site.settings.settings as settings
from wsrc.utils import timezones

from django.contrib.auth.forms import PasswordChangeForm
from django.forms.widgets import Select, CheckboxSelectMultiple
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse as reverse_url
from django.db import transaction
from django.forms import ModelForm, TextInput
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_safe

import rest_framework.generics as rest_generics
from rest_framework import serializers
from rest_framework.parsers import JSONParser
from rest_framework.views import APIView

import markdown
import datetime
import urllib
import httplib
import httplib2
import logging
import time

FACEBOOK_GRAPH_URL              = "https://graph.facebook.com/"
FACEBOOK_GRAPH_ACCESS_TOKEN_URL = FACEBOOK_GRAPH_URL + "oauth/access_token"

WSRC_FACEBOOK_PAGE_ID = 576441019131008
COURT_SLOT_LENGTH = datetime.timedelta(minutes=45)

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
    midnight_today = now - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds = now.microsecond)
    cutoff_today = midnight_today + datetime.timedelta(hours=7)
    midnight_tomorrow = midnight_today + datetime.timedelta(days=1)
    bookings = BookingSystemEvent.objects.filter(start_time__gte=cutoff_today, start_time__lt=midnight_tomorrow).order_by('start_time')
    ctx["bookings"] = bookings
    ctx["today"] = timezones.as_iso_date(now)
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
    
def change_password_view(request):
    if not request.user.is_authenticated():
        return redirect('/login/?next=%s' % request.path)

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

def admin_mailshot_view(request):
    if not request.user.is_authenticated() or not request.user.is_staff:
        raise PermissionDenied()
    from_email_addresses = ["chairman", "clubnight", "committee", "juniors", "membership", "secretary", "tournaments", "treasurer", "webmaster"]
    def get_comp_entrants(group_type):
        group = CompetitionGroup.objects.filter(comp_type=group_type).get(active=True)
        player_ids = set()
        for comp in group.competition_set.all():
            for entrants in comp.entrant_set.all():
                player_ids.add(entrants.player.id)
                if entrants.player2 is not None:
                    player_ids.add(entrants.player2.id)
        return player_ids
    ctx = {
        "players": Player.objects.filter(user__is_active=True),
        "from_email_addresses": [x + "@wokingsquashclub.org" for x in from_email_addresses],
        "membership_types": Player.MEMBERSHIP_TYPES,
        "tournament_player_ids": get_comp_entrants("wsrc_tournaments"),
        "box_player_ids": get_comp_entrants("wsrc_boxes"),
        }
    return TemplateResponse(request, 'mailshot.html', ctx)

class SendEmail(APIView):
    parser_classes = (JSONParser,)
    def put(self, request, format="json"):
        if not request.user.is_authenticated() or not request.user.is_staff:
            raise PermissionDenied()
        email_data = request.DATA
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
   
class NotifierEventFilterForm(ModelForm):
    class Meta:
        time_choices = [
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
        model = EventFilter
        fields = ["earliest", "latest", "notice_period_minutes", "days"]
        exclude = ('user',)
        widgets = {
            "earliest": Select(choices=time_choices),
            "latest": Select(choices=time_choices),
            "notice_period_minutes": Select(choices=notice_period_choices),
            "days": CheckboxSelectMultiple(),
        }

class InfoForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(InfoForm, self).__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
          self.fields['membership_id'].widget.attrs['readonly'] = "readonly"
          self.fields['membership_id'].widget.attrs['disabled'] = "disabled"
        if instance and instance.pk:
          self.fields['membership_type'].widget.attrs['disabled'] = "disabled"
        if instance and instance.pk:
          self.fields['squashlevels_id'].widget.attrs['readonly'] = "readonly"
          self.fields['squashlevels_id'].widget.attrs['disabled'] = "disabled"
    class Meta:
        model = Player
        fields = ["membership_type",  "membership_id",  "squashlevels_id"]
        exclude = ('user',)

def settings_view(request):
    if not request.user.is_authenticated():
        return redirect(reverse_url("django.contrib.auth.views.login") + '?next=%s' % request.path)

    success = False
    events = EventFilter.objects.filter(player=request.user.player)
    if request.method == 'POST': 
        pform = PlayerForm(request.POST, instance=request.user.player)
        uform = UserForm(request.POST, instance=request.user)
        if pform.is_valid() and uform.is_valid(): 
            with transaction.atomic():
                pform.save()
                uform.save()
            success = True
        if len(events) > 0:
            eform = NotifierEventFilterForm(request.POST, instance=events[0])
        else:
            eform = NotifierEventFilterForm(request.POST)
        if eform.is_valid():
            eform.save()
        
    else:
        pform = PlayerForm(instance=request.user.player)
        uform = UserForm(instance=request.user)
        if len(events) > 0:
            eform = NotifierEventFilterForm(instance=events[0])
        else:
            eform = NotifierEventFilterForm()

    iform = InfoForm(instance=request.user.player)

    return render(request, 'settings.html', {
        'player_form':     pform,
        'user_form':       uform,
        'info_form':       iform,
        'evt_filter_form': eform,
        'form_saved':      success,
    })

class DateTimeTzAwareField(serializers.DateTimeField):
    def to_representation(self, value):
        value = timezone.localtime(value) # convert UTC value in DB to local time
        return super(DateTimeTzAwareField, self).to_representation(value)

class BookingSerializer(serializers.ModelSerializer):
    start_time = DateTimeTzAwareField()
    end_time   = DateTimeTzAwareField()
    class Meta:
      model = BookingSystemEvent

class BookingList(rest_generics.ListAPIView):
    serializer_class = BookingSerializer
    def get_queryset(self):
        queryset = BookingSystemEvent.objects.order_by("start_time")
        date = self.request.QUERY_PARAMS.get('date', None)
        if date is not None:
            date = timezones.parse_iso_date_to_naive(date)
            date = datetime.datetime.combine(date, datetime.time(0, tzinfo=timezone.get_default_timezone()))
            delta = self.request.QUERY_PARAMS.get('day_offset', None)
            if delta is not None:
              date = date + datetime.timedelta(days=int(delta))
            tplus1 = date + datetime.timedelta(days=1)
            queryset = queryset.filter(start_time__gte=date, start_time__lt=tplus1)
        return queryset
    
