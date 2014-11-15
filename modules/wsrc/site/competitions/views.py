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

import rest_framework.filters
import rest_framework.views as rest_views
from django.shortcuts import get_object_or_404
import rest_framework.generics as rest_generics
import django.views.generic as view_generics
from django.template.response import TemplateResponse

from wsrc.site.usermodel.models import Player
from wsrc.site.competitions.models import Competition, CompetitionGroup, Match
from wsrc.site.competitions.serializers import PlayerSerializer, CompetitionSerializer, CompetitionGroupSerializer

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

class CompetitionGroupView(rest_generics.RetrieveUpdateDestroyAPIView):
    queryset = CompetitionGroup.objects.all()
    serializer_class = CompetitionGroupSerializer

class MatchDetail(rest_generics.RetrieveUpdateDestroyAPIView):
    model = Match


# HTML template views:

def boxes_view(request, group_id):
    """Return a view of the Leagues for identifier GROUP_ID. If
    GROUP_ID is zero or negative, the nth-previous League set is
    shown"""

    queryset = CompetitionGroup.objects
    offset = None 
    idx = int(group_id)
    if idx < 1:
        offset = - idx
    if offset is not None:        
        group = queryset.filter(comp_type="wsrc_boxes", active=True).order_by('-end_date')[offset]
    else:
        group = get_object_or_404(queryset, id=group_id)

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
    ctx = {"maxplayers": 0, "name": group.name, "id": group.id}
    for league in group.competitions.all():
        cfg = create_box_config(last, league, ctx)
        boxes.append(cfg)
        last = cfg
    for box in boxes:
        while len(box["players"]) < ctx["maxplayers"]:
            box["players"].append(nullplayer)
    ctx["boxes"] = boxes
    return TemplateResponse(request, "boxes.html", {"league_config": ctx, "local_links": False})
    
    
class Boxes(view_generics.ListView):
    filter_backends = [rest_framework.filters.OrderingFilter]
    ordering = ("-end_date")
    template_name = "boxes.html"
    def get_queryset(self):
        return CompetitionGroup.objects.filter(comp_type__name=self.kwargs.get("comp_type"))

