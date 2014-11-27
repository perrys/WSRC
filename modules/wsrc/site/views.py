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

from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404
from wsrc.site.models import PageContent, SquashLevels, SquashLevelsVersion, LeagueMasterFixtures
import markdown

def get_pagecontent_ctx(page):
    data = get_object_or_404(PageContent, page__iexact=page)
    return {
        "pagedata": {
            "title": data.page,
            "content": markdown.markdown(data.markup),
            "last_updated": data.last_updated,
            }
        }



def generic_view(request, page):
    ctx = get_pagecontent_ctx(page)
    return TemplateResponse(request, 'generic_page.html', ctx)

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
    versions = SquashLevelsVersion.objects.filter(is_current=True).order_by('-asof_date')
    if len(versions) > 0:
        latest = versions[0]
        levels = SquashLevels.objects.filter(version=latest).order_by('-level')
        ctx["squashlevels"] = levels
        leaguemasterfixtures = LeagueMasterFixtures.objects.all()
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
                d["scores"] = "%d-%d" % (f.team1_score, f.team2_score)
                d["points"] = "%d-%d" % (f.team1_points, f.team2_points)
                if f.team1_points > f.team2_points:
                    d["class"] = "won"
                elif f.team1_points < f.team2_points:
                    d["class"] = "lost"
            elif not found_empty:
                found_empty = True
                ctx["leaguemaster_last_result_idx"] = idx
            rich_fixtures.append(d)
            
        ctx["leaguemaster"] = rich_fixtures
    return TemplateResponse(request, 'index.html', ctx)
        
    
    
