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

import markdown
import datetime
import urllib
import httplib2

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views.decorators.http import require_safe

from wsrc.site.models import PageContent, SquashLevels, LeagueMasterFixtures, BookingSystemEvent

FACEBOOK_URL="https://www.facebook.com/feeds/page.php"
WSRC_FACEBOOK_PAGE_ID = 576441019131008

def get_pagecontent_ctx(page):
    data = get_object_or_404(PageContent, page__iexact=page)
    return {
        "pagedata": {
            "title": data.page,
            "content": markdown.markdown(data.markup),
            "last_updated": data.last_updated,
            }
        }

@require_safe
def generic_view(request, page):
    ctx = get_pagecontent_ctx(page)
    return TemplateResponse(request, 'generic_page.html', ctx)

@require_safe
def index_view(request):
    TEAMS = {
        u"Woking 1": "1sts",
        u"Woking 2": "2nds",
        u"Woking 3": "3rds",
        u"Woking 4": "4ths",
        }        
    REPLACEMENTS = {
        "Racquets": "R.",
        "Nuffield": "Nuf'ld",
        "Cannons": "Can's",
        "David Lloyd": "D. Lloyd",
        "Virgin Active": "V. Active",
        "Tennis & Squash": "T. & S.",
        "Surrey Sports Park": "Surrey S. P.",
        }        

    ctx = get_pagecontent_ctx('home')
    levels = SquashLevels.objects.all().order_by('-level')
    if len(levels) > 0:
        ctx["squashlevels"] = levels

    leaguemasterfixtures = LeagueMasterFixtures.objects.all().order_by('date')
    rich_fixtures = []
    found_empty = False
    for idx,f in enumerate(leaguemasterfixtures):
        opponents = f.opponents
        for k,v in REPLACEMENTS.iteritems():
            opponents = opponents.replace(k,v)
        d = {
            "date": f.date,
            "team": TEAMS[f.team],
            "opponents": opponents,
            "home_or_away": f.home_or_away,
            "scores": None,
            "points": None,
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
        rich_fixtures.append(d)
    ctx["leaguemaster"] = rich_fixtures

    now = timezone.now()
    midnight_today = now - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds = now.microsecond)
    cutoff_today = midnight_today + datetime.timedelta(hours=17)
    midnight_tomorrow = midnight_today + datetime.timedelta(days=1)
    bookings = BookingSystemEvent.objects.filter(start_time__gte=cutoff_today, start_time__lt=midnight_tomorrow).order_by('start_time')
    ctx["bookings"] = bookings
    return TemplateResponse(request, 'index.html', ctx)
        
    
@require_safe
def facebook_view(request):
    params = {
        "format": "json",
        "id": WSRC_FACEBOOK_PAGE_ID,
        }
    url = FACEBOOK_URL +  "?" + urllib.urlencode(params)
    h = httplib2.Http()
    (resp_headers, content) = h.request(url, "GET")
    return HttpResponse(content, content_type="application/json")
    
