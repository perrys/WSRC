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
from wsrc.site.competitions.models import Competition, CompetitionGroup, Match, Entrant
from wsrc.site.competitions.serializers import PlayerSerializer, CompetitionSerializer, CompetitionGroupSerializer
from wsrc.utils.timezones import parse_iso_date_to_naive

from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.forms import ModelForm, ModelChoiceField
from django.http import HttpResponse, HttpResponseBadRequest

import rest_framework.filters
import rest_framework.generics as rest_generics
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import JSONParser
from rest_framework.views import APIView

import tournament

class FakeRequestContext:
    def __init__(self):
        self.GET = {"expand":True}

FAKE_REQUEST_CONTEXT = FakeRequestContext()
JSON_RENDERER = JSONRenderer()

# REST data views:

class PlayerList(rest_generics.ListAPIView):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer

class PlayerDetail(rest_generics.RetrieveAPIView):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer

class CompetitionList(rest_generics.ListCreateAPIView):
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

class CompetitionGroupList(rest_generics.ListCreateAPIView):
    queryset = CompetitionGroup.objects.all()
    serializer_class = CompetitionGroupSerializer

class CompetitionGroupDetail(rest_generics.RetrieveUpdateDestroyAPIView):
    queryset = CompetitionGroup.objects.all()
    serializer_class = CompetitionGroupSerializer

class UpdateMatch(APIView):
    parser_classes = (JSONParser,)
    def put(self, request, pk, format="json"):
        if not request.user.is_authenticated():
            raise PermissionDenied()
        match_id = int(pk)
        match_data = request.DATA
        if int(match_data["id"]) != match_id:
            raise SuspiciousOperation()
        match = Match.objects.get(pk=match_id)
        walkover = match_data.get("walkover")
        winners = None
        if walkover is not None:
            match.walkover = walkover
            if walkover == 1:
                winners = [match.team1_player1, match.team1_player2]
            else:
                winners = [match.team2_player1, match.team2_player2]
        else:
          wins = [0,0]
          for j in range(1,6):
            scores = []  
            for i in range(1,3):
                  field = "team%(i)d_score%(j)d" % locals()
                  setattr(match, field, match_data[field])
                  scores.append(match_data[field])
            if scores[0] > scores[1]:
              wins[0] += 1
            elif scores[0] < scores[1]:
              wins[1] += 1
          if wins[0] > wins[1]:
              winners = [match.team1_player1, match.team1_player2]
          elif wins[0] < wins[1]:
              winners = [match.team2_player1, match.team2_player2]
        if match.competition.group.comp_type == "wsrc_tournaments":
            if winners is None:
                return HttpResponse("tournament matches must have a winner", status=400)
            tournament.submit_match_winners(match, winners)
        else:
            match.save()
        return HttpResponse(status=201)

class UpdateTournament(APIView):
    parser_classes = (JSONParser,)
    def put(self, request, pk, format="json"):
        if not request.user.is_authenticated():
            raise PermissionDenied()
        comp_id = int(pk)
        comp_data = request.DATA
        if comp_data["id"] != comp_id:
            raise SuspiciousOperation()
        competition = Competition.objects.get(pk=comp_id)
        if competition.state != "not_started":
            raise PermissionDenied()
        entrants = comp_data["entrants"]
        tournament.reset(comp_id, entrants)
        rounds = comp_data["rounds"]
        if rounds:
            tournament.set_rounds(comp_id, rounds)
        return HttpResponse(status=201)
    

# HTML template views:

def get_competition_lists():
    tournaments = []
    for group in CompetitionGroup.objects.filter(comp_type="wsrc_tournaments"):
        tournaments.append({"year": group.end_date.year, "competitions": group.competition_set.exclude(state="not_started").order_by("name")})
    leagues = []
    for group in CompetitionGroup.objects.filter(comp_type="wsrc_boxes"):
        leagues.append({"year": group.end_date.year, "end_date": group.end_date, "name": group.name})
    return {
        "tournaments": tournaments,
        "leagues": leagues,
        }

def boxes_view(request, end_date=None, template_name="boxes.html"):
    """Return a view of the Leagues for ending on END_DATE. If
    END_DATE is  negative, the current league is shown"""

    queryset = CompetitionGroup.objects
    if end_date is None:
        group = queryset.filter(comp_type="wsrc_boxes", active=True).order_by('-end_date')[0]
    else:
        end_date = parse_iso_date_to_naive(end_date)
        group = get_object_or_404(queryset, end_date=end_date)

    box_data = JSON_RENDERER.render(CompetitionGroupSerializer(group, context={"request": FAKE_REQUEST_CONTEXT}).data)
    competition_groups = JSON_RENDERER.render(CompetitionGroupSerializer(CompetitionGroup.objects.all(), many=True).data)

    def create_box_config(previous_comp, competition, ctx):
        is_second = False
        ctx["maxplayers"] = max(ctx["maxplayers"], len(competition.entrant_set.all()))
        if previous_comp is not None:
            if previous_comp["name"][:-1] == competition.name[:-1]: # e.g. "League 1A" vs "League 1B"
                is_second = True
                previous_comp["colspec"] = 'double'
                previous_comp["nthcol"] = 'first'
        return {"colspec": is_second and "double" or "single",
                "nthcol": is_second and 'second' or 'first',
                "name": competition.name,
                "id": competition.id,
                "players": [p.player for p in competition.entrant_set.all().order_by("ordering")]
                }

    def create_new_box_config(idx):
        result = {"id": None, "players": None}
        if idx == 0:
            result["colspec"] = "single"
            result["name"] = "Premier"
            result["nthcol"] = "first"
        else:
            result["colspec"] = "double"
            suffix = (idx % 2 == 1) and "A" or "B"
            number = (idx+1)/2
            result["name"] = "League %(number)d%(suffix)s" % locals()
            result["nthcol"] = suffix == "A" and "first" or "second"
        return result

    new_boxes = [create_new_box_config(i) for i in range(0,21)]

    nullplayer = {"name": "", "id": ""}
    last = None
    boxes = []
    comp_meta = {"maxplayers": 0, "name": group.name, "id": group.id}
    ctx = {"competition": comp_meta}
    for league in group.competition_set.all():
        cfg = create_box_config(last, league, comp_meta)
        boxes.append(cfg)
        last = cfg
    for box in boxes:
        while len(box["players"]) < comp_meta["maxplayers"]:
            box["players"].append(nullplayer)
    ctx["boxes"] = boxes
    ctx["new_boxes"] = new_boxes
    ctx["competition_groups"] = competition_groups
    ctx.update(get_competition_lists())
    ctx["box_data"] = box_data
    ctx['players'] = Player.objects.all()
    return TemplateResponse(request, template_name, ctx)
    
    

def bracket_view(request, year, name, template_name="tournaments.html"):
    if year is None:
        groups = CompetitionGroup.objects.filter(comp_type='wsrc_tournaments').filter(active=True).order_by("-end_date")
        group = groups[0]
        print group
    else:
        group = get_object_or_404(CompetitionGroup.objects, end_date__year=year, comp_type='wsrc_tournaments')

    name = name.replace("_", " ")        
    competition = get_object_or_404(group.competition_set, name__iexact=name)

    bracket_data = JSON_RENDERER.render(CompetitionSerializer(competition, context={"request": FAKE_REQUEST_CONTEXT}).data)
    html_table = tournament.render_tournament(competition)

    ctx = {"competition": competition, "bracket": html_table, "bracket_data": bracket_data}
    ctx.update(get_competition_lists())
    
    return TemplateResponse(request, template_name, ctx)

class NewCompetitionGroupForm(ModelForm):
    class Meta:
        model = CompetitionGroup
        fields = ["name", "comp_type", "end_date"]

class NewTournamentForm(ModelForm):
    group = ModelChoiceField(queryset=CompetitionGroup.objects.filter(comp_type = "wsrc_tournaments"),
                             initial=CompetitionGroup.objects.filter(comp_type = "wsrc_tournaments").order_by('-end_date')[0])
    class Meta:
        model = Competition
        fields = ["name", "end_date", "group", "state"]

class EditTournamentForm(ModelForm):
    class Meta:
        model = Competition
        fields = ["name"]

def bracket_admin_view(request, year=None, name=None):
    if not request.user.is_authenticated():
        raise PermissionDenied()

    competition = None
    comp_data = '{}'
    if name is not None:
        group = get_object_or_404(CompetitionGroup.objects, end_date__year=year, comp_type='wsrc_tournaments')
        name = name.replace("_", " ")        
        competition = get_object_or_404(group.competition_set, name__iexact=name)
        comp_data = JSON_RENDERER.render(CompetitionSerializer(competition, context={"request": FAKE_REQUEST_CONTEXT}).data)

    new_group_form        = None
    new_tournament_form   = None
    edit_tournament_form  = None
    success_message = None

    if request.method == 'POST': 

        queryDict = request.POST
        action = request.POST.get("action", None)
        if action == "new_comp_group":
            new_group_form = NewCompetitionGroupForm(request.POST, auto_id='id_groupform_%s')
            if new_group_form.is_valid(): 
                new_group_form.save()            
                new_group_form.success_message = "created group " + str(new_group_form.instance)
        elif action == "new_tournament":
            new_tournament_form = NewTournamentForm(request.POST, auto_id='id_compform_%s')
            if new_tournament_form.is_valid(): 
                new_tournament_form.save()            
                new_tournament_form.success_message = "created tournament " + str(new_tournament_form.instance)
        else:
            return HttpResponseBadRequest("<h1>invalid form data</h1>")

    if new_tournament_form is None:
        new_tournament_form   = NewTournamentForm(auto_id='id_compform_%s')
    if new_group_form is None:
        new_group_form        = NewCompetitionGroupForm(auto_id='id_groupform_%s')
    if edit_tournament_form is None:
        edit_tournament_form  = EditTournamentForm(auto_id='id_editform_%s', instance=competition)

    tournaments = []
    for group in CompetitionGroup.objects.filter(comp_type="wsrc_tournaments"):
        tournaments.append({"year": group.end_date.year, "competitions": group.competition_set.all()})
        
    return render(request, 'tournaments_admin.html', {
        'edit_tournament_form': edit_tournament_form,
        'new_tournament_form':  new_tournament_form,
        'new_group_form':       new_group_form,
        'players':              Player.objects.filter(user__is_active=True),
        'competition_data':     comp_data,
        'tournaments':          tournaments,
    })
