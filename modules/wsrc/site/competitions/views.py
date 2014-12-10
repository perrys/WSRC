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

from wsrc.site.usermodel.models import Player
from wsrc.site.competitions.models import Competition, CompetitionGroup, Match
from wsrc.site.competitions.serializers import PlayerSerializer, CompetitionSerializer, CompetitionGroupSerializer
from wsrc.utils.timezones import parse_iso_date_to_naive

from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

import rest_framework.filters
import rest_framework.generics as rest_generics

import tournament

# REST data views:

class PlayerList(rest_generics.ListAPIView):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer

class PlayerDetail(rest_generics.RetrieveAPIView):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer

class CompetitionList(rest_generics.ListAPIView):
    serializer_class = CompetitionSerializer
    filter_backends = [rest_framework.filters.OrderingFilter]
    ordering_fields = ("__all__")
    def get_queryset(self):
        queryset = Competition.objects.all()
        year = self.request.QUERY_PARAMS.get('year', None)
        if year is not None:
            queryset = queryset.filter(end_date__year=year)
        return queryset

class CompetitionDetail(rest_generics.RetrieveUpdateDestroyAPIView):
    queryset = Competition.objects.all()
    serializer_class = CompetitionSerializer

class CompetitionGroupList(rest_generics.ListAPIView):
    model = CompetitionGroup

class CompetitionGroupDetail(rest_generics.RetrieveUpdateDestroyAPIView):
    queryset = CompetitionGroup.objects.all()
    serializer_class = CompetitionGroupSerializer

class MatchDetail(rest_generics.RetrieveUpdateDestroyAPIView):
    model = Match

class MatchCreate(rest_generics.CreateAPIView):
    model = Match

# HTML template views:

def get_competition_lists():
    tournaments = []
    for group in CompetitionGroup.objects.filter(comp_type="wsrc_tournaments"):
        tournaments.append({"year": group.end_date.year, "competitions": group.competitions.all()})
    return {
        "tournaments": tournaments,
        }

def boxes_view(request, end_date=None):
    """Return a view of the Leagues for ending on END_DATE. If
    END_DATE is  negative, the current league is shown"""

    queryset = CompetitionGroup.objects
    if end_date is None:
        group = queryset.filter(comp_type="wsrc_boxes", active=True).order_by('-end_date')[0]
    else:
        end_date = parse_iso_date_to_naive(end_date)
        group = get_object_or_404(queryset, end_date=end_date)

    def create_box_config(previous_comp, competition, ctx):
        is_second = False
        ctx["maxplayers"] = max(ctx["maxplayers"], len(competition.players.all()))
        if previous_comp is not None:
            if previous_comp["name"][:-1] == competition.name[:-1]: # e.g. "League 1A" vs "League 1B"
                is_second = True
                previous_comp["colspec"] = 'double'
                previous_comp["nthcol"] = 'first'
        return {"colspec": is_second and "double" or "single",
                "nthcol": is_second and 'second' or 'first',
                "name": competition.name,
                "id": competition.id,
                "players": [p for p in competition.players.all()]
                }

    nullplayer = {"name": "", "id": ""}
    last = None
    boxes = []
    comp_meta = {"maxplayers": 0, "name": group.name, "id": group.id}
    ctx = {"competition": comp_meta}
    for league in group.competitions.all():
        cfg = create_box_config(last, league, comp_meta)
        boxes.append(cfg)
        last = cfg
    for box in boxes:
        while len(box["players"]) < comp_meta["maxplayers"]:
            box["players"].append(nullplayer)
    ctx["boxes"] = boxes
    ctx.update(get_competition_lists())
    return TemplateResponse(request, "boxes.html", ctx)
    
    

def bracket_view(request, year, name):
    if year is None:
        group = get_object_or_404(CompetitionGroup.objects, end_date__year=2014, comp_type='wsrc_tournaments') # TODO: get latest active
    else:
        group = get_object_or_404(CompetitionGroup.objects, end_date__year=year, comp_type='wsrc_tournaments')

    name = name.replace("_", " ")        
    competition = get_object_or_404(group.competitions, name__iexact=name)

    html_table = tournament.render_tournament(competition)

    ctx = {"competition": competition, "bracket": html_table}
    ctx.update(get_competition_lists())
    
    return TemplateResponse(request, "tournaments.html", ctx)
    
