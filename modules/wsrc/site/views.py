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

from wsrc.site.models import PageContent, SquashLevels, LeagueMasterFixtures, BookingSystemEvent
from wsrc.site.usermodel.models import Player
import wsrc.site.settings.settings as settings
from wsrc.utils import timezones

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse as reverse_url
from django.db import transaction
from django.forms import ModelForm
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_safe

import rest_framework.generics as rest_generics
from rest_framework import serializers

import markdown
import datetime
import urllib
import httplib
import httplib2
import logging

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
        "debug": True,
        }
    return result

@require_safe
def generic_view(request, page):
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
    
    def refresh_auth_token():
      LOGGER.info("Refreshing Facebook access token...")
      params = {
          "grant_type":    "client_credentials",
          "client_id" :    settings.FB_APP_ID,
          "client_secret": settings.FB_APP_SECRET,
          }
      url = FACEBOOK_GRAPH_ACCESS_TOKEN_URL +  "?" + urllib.urlencode(params)
      return fb_get(url)

    token = refresh_auth_token()

    url = FACEBOOK_GRAPH_URL + str(WSRC_FACEBOOK_PAGE_ID) + "/feed?" + token
    try:
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

class UserForm(ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "username",  "email"]

class PlayerForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(PlayerForm, self).__init__(*args, **kwargs)
        self.fields["squashlevels_id"].label = "SquashLevels ID"
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
          self.fields['squashlevels_id'].widget.attrs['readonly'] = True
          self.fields['squashlevels_id'].widget.attrs['disabled'] = "disabled"
    class Meta:
        model = Player
        fields = ["cell_phone", "other_phone", "short_name",  "squashlevels_id"]
        exclude = ('user',)


def settings_view(request):
    if not request.user.is_authenticated():
        return redirect(reverse_url(django.contrib.auth.views.login) + '?next=%s' % request.path)

    success = False
    if request.method == 'POST': 
        pform = PlayerForm(request.POST, instance=request.user.player)
        uform = UserForm(request.POST, instance=request.user)
        if pform.is_valid() and uform.is_valid(): 
            with transaction.atomic():
                pform.save()
                uform.save()
            success = True
    else:
        
        pform = PlayerForm(instance=request.user.player)
        uform = UserForm(instance=request.user)

    return render(request, 'settings.html', {
        'player_form': pform,
        'user_form':   uform,
        'form_saved': success,
    })


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
      model = BookingSystemEvent

class BookingList(rest_generics.ListAPIView):
    serializer_class = BookingSerializer
    def get_queryset(self):
        queryset = BookingSystemEvent.objects.order_by("start_time")
        date = self.request.QUERY_PARAMS.get('date', None)
        if date is not None:
            date = timezones.parse_iso_date_to_naive(date)
            delta = self.request.QUERY_PARAMS.get('day_offset', None)
            if delta is not None:
              date = date + datetime.timedelta(days=int(delta))
            tplus1 = date + datetime.timedelta(days=1)
            queryset = queryset.filter(start_time__gte=date, start_time__lt=tplus1)
        return queryset
    
