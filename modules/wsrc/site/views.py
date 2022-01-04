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

from wsrc.site.models import PageContent, SquashLevels, LeagueMasterFixtures, MaintenanceIssue,\
    Suggestion, ClubEvent, CommitteeMeetingMinutes, NavigationLink, OAuthAccess
from wsrc.site.competitions.models import CompetitionGroup
from wsrc.site.courts.models import BookingSystemEvent
from wsrc.site.email.models import VirtualAlias, VirtualDomain
from wsrc.site.usermodel.models import Player, SubscriptionType
import wsrc.site.settings.settings as settings
from wsrc.utils import timezones, email_utils, url_utils

from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import views as auth_views, authenticate
from django.forms.fields import CharField, IntegerField
from django.forms.widgets import Textarea, HiddenInput
from django.middleware.csrf import get_token
from django.core.mail import SafeMIMEMultipart, SafeMIMEText
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.urls import reverse_lazy
from django.db import transaction
from django.forms import ModelForm, TextInput
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.template import Template, Context, RequestContext
from django.template.response import TemplateResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_safe, require_http_methods
from django.views.generic.edit import CreateView
from django.db.models import Q

import rest_framework.generics as rest_generics
from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import ValidationError as RestValidationError
from rest_framework import serializers
from rest_framework.parsers import JSONParser, FormParser
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
from bs4 import BeautifulSoup


WSRC_FACEBOOK_PAGE_ID = 576441019131008
COURT_SLOT_LENGTH = datetime.timedelta(minutes=45)

COMMITTEE_EMAIL_ADDRESS     = "committee@wokingsquashclub.org"
MAINT_OFFICER_EMAIL_ADRESS  = "maintenance@wokingsquashclub.org"
BOOKING_SYSTEM_EMAIL_ADRESS = "court_booking@wokingsquashclub.org"

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
LW_REQUEST = collections.namedtuple('LW_REQUEST', ['query_params', 'user'])

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.WARNING)

def get_pagecontent_ctx(page, title=None):
    data = get_object_or_404(PageContent, page__iexact=page)
    result = {
        "pagedata": {
            "title": title is not None and title or data.page.replace("_", " "),
            "raw_content": data.markup,
            "content": markdown.markdown(data.markup, extensions=["markdown.extensions.toc", "markdown.extensions.attr_list", \
                                                                  "markdown.extensions.smarty", "markdown.extensions.extra"]),
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
def generic_nav_view(request, page, template):
    "Specialized view for the about page which adds a navigation tree dynamically"
    ctx = get_pagecontent_ctx(page)
    # parse the content to find the IDs of title (H3,H4) elements,
    # which were inserted by the Markdown TOC extension, and use those
    # to form a navigation tree..
    content = ctx["pagedata"]["content"]
    maindoc = BeautifulSoup(content, "html.parser")
    navtree = BeautifulSoup("<ul class='nav'></ul>", "html.parser")
    def subelement(parent, child_tag, text=None, class_=None, **kwargs):
        tag = navtree.new_tag(child_tag, **kwargs)
        if text is not None:
            tag.string = text
        if class_ is not None:
            tag["class"] = class_
        if parent is not None:
            parent.append(tag)
        return tag
    last_ul = None
    for header in maindoc.find_all(["h3", "h4"]):
        pending = None
        if header.name == "h3":            
            item = subelement(navtree.ul, "li")
            pending = subelement(None, "ul", class_="nav")
        else:
            item = subelement(last_ul, "li")
        subelement(item, "a", text=header.string, href='#{uid}'.format(uid=header['id']))
        if pending:
            last_ul = pending
            item.append(pending)
    ctx["pagedata"]["navtree"] = str(navtree.ul)
    return TemplateResponse(request, template, ctx)

@require_safe
def generic_txt_view(request, page):
    "Simple text format view"
    ctx = get_pagecontent_ctx(page)
    return TemplateResponse(request, 'generic_page.txt', ctx, content_type="text/plain")

@require_safe
@login_required
def committee_view(request):
    from .navigation import NavigationMiddleWare
    # need a two-pass render for the committee page
    page = 'Committee'
    ctx = get_pagecontent_ctx(page, "Management")
    template = Template(ctx["pagedata"]["content"])
    ctx["pagedata"]["content"] = template.render(Context({'meetings': CommitteeMeetingMinutes.objects.all()}))
    return TemplateResponse(request, 'generic_page.html', ctx)


def generate_tokens(date):
    start_times = {
        1: datetime.datetime.combine(date, datetime.time(8, 15)),
        2: datetime.datetime.combine(date, datetime.time(8, 30)),
        3: datetime.datetime.combine(date, datetime.time(8, 45)),
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
    levels = SquashLevels.objects.values('name', 'level', 'player__squashlevels_id').order_by('-level')
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
    bookings = BookingSystemEvent.get_bookings_for_date(now)

    fake_context = {"request": LW_REQUEST({"date": today_str}, user=request.user)}
    bookings_data = BookingSerializer(bookings, many=True, context=fake_context).data

    ctx["bookings"] = JSON_RENDERER.render(bookings_data)
    ctx["today"] = today_str
    return TemplateResponse(request, 'index.html', ctx)


@require_safe
def facebook_view(request):
    "Proxy view for the FB graph data from the WSRC page feed"

    class FBException(Exception):
        def __init__(self, message, errortype, statuscode):
            super(FBException, self).__init__(message)
            self.statuscode = statuscode
            self.errortype = errortype

    oauth_record = get_object_or_404(OAuthAccess, name="Facebook")

    def fb_get():
        url = oauth_record.auth_server_uri + "/v3.2/" + str(WSRC_FACEBOOK_PAGE_ID) + "/feed"
        params = {
            # no longer have to pre-request an access token, can just provide ids from server-side call:
            "access_token": "{id}|{secret}".format(id=oauth_record.client_id, secret=oauth_record.client_secret)
        }
        url += "?" + urllib.urlencode(params)
        (resp_headers, content) = url_utils.request(url, "GET")
        if resp_headers.status != httplib.OK:
            LOGGER.error("unable to fetch FB data, status = " + str(resp_headers.status) + ", response: " +  content)
            exception = None
            if len(content) > 0:
                try:
                    response = json.loads(content)
                    error = response.get("error")
                    if error is not None:
                        exception = FBException(error.get("message"), error.get("type"), error.get("code"))
                except:
                    pass
            if exception is None:
                exception = FBException(content or "(no content)", resp_headers.reason, resp_headers.status)
            raise exception
        return content

    try:
        # the response is JSON so pass it straight through
        data = fb_get()
        return HttpResponse(data, content_type="application/json")
    except FBException, e:
        msg = "ERROR: Unable to fetch Facebook page: {msg} [{code}] - {type}".format(msg=str(e), code=e.statuscode, type=e.errortype)
        return HttpResponse(content=msg,
                            content_type="text/plain",
                            status=httplib.SERVICE_UNAVAILABLE)

@require_safe
def kiosk_view(request):
    return TemplateResponse(request, 'kiosk.html', {})

def login(request, *args, **kwargs):
    last_username = request.COOKIES.get("last_username")
    session_timeout = request.COOKIES.get("session_timeout")
    disable_remember_username = request.COOKIES.get("disable_remember_username")
    response = auth_views.login(request, *args, **kwargs)
    if request.method == "POST":
        if request.POST.get("remember_username"):
            last_username = request.POST.get("username")
            if last_username is not None and response.status_code == 302:
                response.set_cookie("last_username", last_username, max_age = 30 * 24 * 60 * 60)
        else:
            response.delete_cookie("last_username")
            last_username = None
        if "disable_remember_username" in request.POST:
            disable_remember_username = request.POST.get("disable_remember_username") == "1"
            if disable_remember_username:
                response.set_cookie("disable_remember_username", "1", expires=datetime.datetime(2038, 1, 1))
            else:
                response.delete_cookie("disable_remember_username")
        if "session_timeout" in request.POST:
            session_timeout = request.POST.get("session_timeout")
            try:
                session_timeout = int(session_timeout)
                if session_timeout:
                    response.set_cookie("session_timeout", str(session_timeout), expires=datetime.datetime(2038, 1, 1))
                else:
                    response.delete_cookie("session_timeout")                    
            except ValueError:
                LOGGER.exception("invalid session_timeout value")
                session_timeout = None
                
    if hasattr(response, "context_data"):
        if not disable_remember_username and last_username is not None:
            response.context_data["last_username"] = last_username
            response.context_data["remember_username"] = True
        if "show_login_settings" in request.GET:
            response.context_data["show_auto_logout_settings"] = True
            response.context_data["session_timeout"] = session_timeout
            response.context_data["disable_remember_username"] = disable_remember_username
    return response

@login_required
def admin_mailshot_view(request):
    if not request.user.is_staff:
        raise PermissionDenied()
    from_domain = VirtualDomain.objects.first()
    from_email_addresses = [e for e in VirtualAlias.objects.filter(from_domain=from_domain).values_list("from_username", flat=True).distinct()]
    def get_comp_entrants(*group_types):
        players = CompetitionGroup.get_comp_entrants(*group_types)
        return [player.id for player in players if player.user.is_active]
    def player_data(p):
        sub = p.get_current_subscription()
        
        return (p.id, {"id": p.id, "full_name": p.user.get_full_name(), "ordered_name": p.get_ordered_name(), "email": p.user.email,
                       "prefs_receive_email": p.prefs_receive_email,
                       "subscription_type": {"name": sub.subscription_type.name if sub else None,
                                             "id": sub.subscription_type.id if sub else None}})
    players = Player.objects.filter(user__is_active=True).select_related("user")\
                   .prefetch_related("subscription_set__subscription_type")
    players = dict([player_data(player) for player in players])
    ctx = {
        "players": JSON_RENDERER.render(players),
        "from_email_addresses": ["{0}@{1}".format(x, from_domain.name) for x in from_email_addresses],
        "subscription_types": SubscriptionType.objects.all(),
        "tournament_player_ids": get_comp_entrants("tournaments", "tournament_qualifiers"),
        "box_player_ids": get_comp_entrants("squash_boxes"),
        "squash57_box_player_ids": get_comp_entrants("squash57_boxes"),
        }    
    return TemplateResponse(request, 'mailshot.html', ctx)

class SendEmail(APIView):
    parser_classes = (JSONParser,FormParser)
    def post(self, request):
        return self.put(request)

    def put(self, request, format="json"):
        if not (request.user.is_authenticated and\
                (request.user.is_staff or\
                 request.user.groups.filter(name="Club Login").count() == 1)):
            raise PermissionDenied()
        email_data = dict(request.data.items()) # ensure we have a native dictionary
        fmt  = email_data.pop('format')
        body = email_data.pop('body')
        if 'to' in email_data:
            email_data["to_list"] = [email_data.pop('to')]
        if fmt == 'mixed':
            email_data['text_body'] = body
            email_data['html_body'] = markdown.markdown(body, extensions=['markdown.extensions.extra'])
        elif fmt == 'text':
            email_data['text_body'] = body
            email_data['html_body'] = None
        elif fmt == 'html':
            email_data['text_body'] = ''
            email_data['html_body'] = body
        debug = False
        if debug:
            import pprint
            print pprint.pprint(email_data)
        else:
            import wsrc.utils.email_utils as email_utils
            email_utils.send_email(**email_data)
        return HttpResponse(status=204)

def notify(template_name, kwargs, subject, to_list, cc_list, from_address, attachments=None):
    text_body, html_body = email_utils.get_email_bodies(template_name, kwargs)
    email_utils.send_email(subject, text_body, html_body, from_address, to_list, cc_list=cc_list, extra_attachments=attachments)

@login_required
def maintenance_view(request):
    issues = [issue for issue in MaintenanceIssue.objects.all().order_by('-reported_date')]
    cmp_map = {'ar': 1, 'aa': 2, 'ni': 3, 'c': 3}
    def status_cmp(x, y):
        return cmp(cmp_map[x.status], cmp_map[y.status])
    issues.sort(status_cmp)

    kwargs = {
        'data': issues,
    }
    return TemplateResponse(request, "maintenance.html", kwargs)

class SuggestionForm(ModelForm):
    class Meta:
        model = Suggestion
        fields = ["description", "suggester"]
    
class MaintenanceForm(ModelForm):
    class Meta:
        model = MaintenanceIssue
        fields = ["description", "reporter"]

class SuggestionCreateView(CreateView):
    template_name = 'suggestion_form.html'
    success_url = reverse_lazy("suggestions")
    form_class = SuggestionForm
    def form_valid(self, form):
        form.instance.suggester = self.request.user.player
        result = super(SuggestionCreateView, self).form_valid(form)
        email_target = COMMITTEE_EMAIL_ADDRESS
        context = {"suggestion": self.object}
        to_list = [self.request.user.email, email_target]
        notify("SuggestionReceipt", context,
               subject="WSRC New Suggestion", to_list=to_list,
               cc_list=None, from_address=COMMITTEE_EMAIL_ADDRESS)
        return result

class MaintenanceIssueCreateView(CreateView):
    template_name = 'suggestion_form.html'
    form_class = MaintenanceForm
    success_url = reverse_lazy("maintenance")
    def get_context_data(self, **kwargs):
        result = super(MaintenanceIssueCreateView, self).get_context_data(**kwargs)
        result["mode"] = "maintenance"
        return result
    def form_valid(self, form):
        form.instance.reporter = self.request.user.player
        result = super(MaintenanceIssueCreateView, self).form_valid(form)
        context = {"issue": self.object}
        to_list = [self.request.user.email, MAINT_OFFICER_EMAIL_ADRESS]
        cc_list = [COMMITTEE_EMAIL_ADDRESS]
        notify("MaintenanceIssueReceipt", context,
               subject="WSRC Maintenance", to_list=to_list,
               cc_list=cc_list, from_address=MAINT_OFFICER_EMAIL_ADRESS)
        return result

@login_required
def suggestions_view(request):
    suggestions = Suggestion.objects.all().order_by('-submitted_date')
    kwargs = {
        'data': suggestions,
    }
    return TemplateResponse(request, 'suggestions.html', kwargs)


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
        fields = ('start_time', 'end_time', 'court', 'name', 'event_type', 'event_id', 'description', 'created_by', 'created_time', 'no_show')
    @classmethod
    def many_init(cls, *args, **kwargs):
        request = kwargs["context"]["request"]
        authenticated = request.user.is_authenticated
        if not authenticated and hasattr(request, "META"):
            authenticated = authenticate(username=request.META.get("HTTP_X_USERNAME"),
                                         password=request.META.get("HTTP_X_PASSWORD"))
        kwargs['child'] = cls() if authenticated\
                          else ObfuscatedBookingSerializer()
        return CustomBookingListSerializer(*args, **kwargs)

class ObfuscatedBookingSerializer(BookingSerializer):
    name = serializers.CharField(source="obfuscated_name", read_only="True")
    
class BookingList(rest_generics.ListAPIView):
    serializer_class = BookingSerializer
    def get_queryset(self):
        date = self.request.query_params.get('date', None)
        if date is None:
            raise RestValidationError("required date parameter not supplied")
        date = timezones.parse_iso_date_to_naive(date)
        date = datetime.datetime.combine(date, datetime.time(0, tzinfo=timezone.get_default_timezone()))
        delta = self.request.query_params.get('day_offset', None)
        if delta is not None:
            date = date + datetime.timedelta(days=int(delta))
        return BookingSystemEvent.get_bookings_for_date(date)

def auth_view(request):
    if request.method == 'GET':
        data = {
            "username": request.user and request.user.username or None,
            "csrf_token": get_token(request)
        }
        response = HttpResponse(json.dumps(data), content_type="application/json")
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
                response = HttpResponse(json.dumps(data), content_type="application/json", status=httplib.OK)
            else:
                response = HttpResponse("inactive login", content_type="text/plain", status=httplib.FORBIDDEN)
        else:
            response = HttpResponse("invalid login", content_type="text/plain", status=httplib.FORBIDDEN)
    elif request.method == 'DELETE':
        logout(request)
        response = HttpResponse(None, content_type="application/json", status=httplib.OK)
    elif request.method == 'OPTIONS':
        response = HttpResponse(None, content_type="application/json", status=httplib.OK)
    else:
        response = HttpResponse("unrecognised method", status=httplib.FORBIDDEN)

    response['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
    return response

class MarkdownField(serializers.Field):
    def to_representation(self, value):
        return markdown.markdown(value, extensions=["markdown.extensions.attr_list"])


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

class OAuthExchangeTokenView(APIView):
    parser_classes = (JSONParser,)
    def put(self, request, record_id):
        # continue only if the user is some kind of membership editor
        if not request.user.has_perm("usermodel.change_player"):
            raise PermissionDenied()
        oauth_record = OAuthAccess.objects.get(pk=record_id)
        temp_access_code = request.data["temporary_access_code"]
        print temp_access_code
        token_uri = oauth_record.auth_server_uri + oauth_record.token_endpoint
        token = url_utils.get_access_token(token_uri,
                                           grant_type="authorization_code",
                                           client_id=oauth_record.client_id,
                                           client_secret=oauth_record.client_secret,
                                           redirect_uri=oauth_record.redirect_uri,
                                           temp_access_code=temp_access_code)
        return HttpResponse(json.dumps({"access_token": token}), status=201)


@require_safe
def generic_get_template_view(request, template_name, **kwargs):
    return TemplateResponse(request, template_name, kwargs)
