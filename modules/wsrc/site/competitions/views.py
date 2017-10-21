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

from wsrc.site.models import EmailContent
from wsrc.site.usermodel.models import Player
from wsrc.site.competitions.models import Competition, CompetitionGroup, Match, Entrant
from wsrc.site.competitions.serializers import CompetitionSerializer, CompetitionGroupSerializer, MatchSerializer, get_box_league_points
from wsrc.utils.html_table import Table, Cell, SpanningCell, merge_classes
from wsrc.utils.timezones import parse_iso_date_to_naive
from wsrc.utils import email_utils

from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.template import Template, Context
from django.template.response import TemplateResponse
from django.forms import ModelForm, ModelChoiceField
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import TemplateView

import rest_framework.filters
import rest_framework.status
import rest_framework.generics as rest_generics
import rest_framework.permissions as rest_permissions
from rest_framework.authentication import SessionAuthentication
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.parsers import JSONParser
from rest_framework.views import APIView

import datetime
import markdown
import StringIO
import os.path
import tournament
from operator import itemgetter

class FakeRequestContext:
    def __init__(self):
        self.GET = {"expand":True}

FAKE_REQUEST_CONTEXT = FakeRequestContext()
JSON_RENDERER = JSONRenderer()

# REST data views:

class CompetitionList(rest_generics.ListCreateAPIView):
    serializer_class = CompetitionSerializer
    filter_backends = [rest_framework.filters.OrderingFilter]
    ordering_fields = ("__all__")
    queryset = Competition.objects.none() # for django model permissions    
    def get_queryset(self):
        queryset = Competition.objects.all()
        year = self.request.QUERY_PARAMS.get('year', None)
        if year is not None:
            queryset = queryset.filter(end_date__year=year)
        return queryset
    authentication_classes = (SessionAuthentication,)
    permission_classes = (rest_permissions.DjangoModelPermissionsOrAnonReadOnly,)

class CompetitionDetail(rest_generics.RetrieveUpdateDestroyAPIView):
    queryset = Competition.objects.all()
    serializer_class = CompetitionSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (rest_permissions.DjangoModelPermissionsOrAnonReadOnly,)

class CompetitionGroupList(rest_generics.ListCreateAPIView):
    queryset = CompetitionGroup.objects.all()
    serializer_class = CompetitionGroupSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (rest_permissions.DjangoModelPermissionsOrAnonReadOnly,)

class CompetitionGroupDetail(rest_generics.RetrieveUpdateDestroyAPIView):
    queryset = CompetitionGroup.objects.all()
    serializer_class = CompetitionGroupSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (rest_permissions.DjangoModelPermissionsOrAnonReadOnly,)

class SelfUpdateOrCompetitionEditorPermission(rest_permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in rest_permissions.SAFE_METHODS:
            return True
        elif request.method == "PUT" or request.method == "PATCH":
            if request.user.has_perm("competitions.change_match"):
                return True
        elif request.method == "POST":
            if request.user.has_perm("competitions.change_match"):
                return True
        elif request.method == "DELETE":
            if request.user.has_perm("competitions.delete_match"):
                return True
        player = get_object_or_404(Player.objects.all(), user=request.user)
        for i in (1,2):
            entrant_id = request.data.get("team%(i)d" % locals())
            entrant = get_object_or_404(Entrant.objects.all(), id=entrant_id)
            if entrant.player1 == player or entrant.player2 == player:
                return True
        return False

            

class UpdateMatch(rest_generics.RetrieveUpdateAPIView):
    queryset = Match.objects.all()
    serializer_class = MatchSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (SelfUpdateOrCompetitionEditorPermission,)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        return self.perform_update(serializer)

    def perform_update(self, serializer):
        match = serializer.instance
        if match.competition.group.comp_type == "wsrc_tournaments":
            # we do some special validation, and create the next match
            # when this is a knockout competition. Validation should
            # really be done by the serializer, but we need the
            # winners for the next step anyway.
            for attr, value in serializer.validated_data.items():
                setattr(match, attr, value)
            winner = match.get_winner()
            if winner is None:
                return HttpResponse("tournament matches must have a winner", status=400)
            tournament.submit_match_winner(match, winner)
        else:
            serializer.save()
        return Response(serializer.data, status=200)

class CreateMatch(rest_generics.CreateAPIView):
    queryset = Match.objects.none()
    serializer_class = MatchSerializer
    authentication_classes = (SessionAuthentication,)
    permission_classes = (SelfUpdateOrCompetitionEditorPermission,)

# HTML template views:

def set_view_options(request, context):
    options = context["options"] = dict()
    for opt in ["no_navigation"]:
        if opt in request.GET:
            options[opt] = True
    return options

def get_tournament_links(options, selected_comp_or_group):
    qset = CompetitionGroup.objects.all() # filter(active=True)
    result = []
    no_navigation = "no_navigation" in options
    suffix = no_navigation and "?no_navigation" or ""
    for group in qset.filter(comp_type="wsrc_tournaments"):
        year = group.end_date.year
        year_suffix = no_navigation and " {year}".format(**locals()) or "" 
        for comp in group.competition_set.exclude(state="not_started").order_by("name"):
            name = comp.name
            result.append({"year": year, 
                           "name": name + year_suffix, 
                           "end_date": comp.end_date,
                           "link": reverse(bracket_view) + "/{year}/{name}/{suffix}".format(**locals()),
                           "selected": no_navigation and comp == selected_comp_or_group
                       })
    for group in qset.filter(comp_type="wsrc_qualifiers", active=True):
        year = group.end_date.year
        year_suffix = no_navigation and " {year}".format(**locals()) or "" 
        name = " ".join(group.name.split()[2:-1]) # remove front and rear sections
        result.append({"year": year, 
                       "name": name + " (qualifier)" + year_suffix, 
                       "end_date": group.end_date,
                       "link": "/tournaments/qualifiers/{year}/{name}{suffix}".format(**locals()),
                       "selected": no_navigation and group == selected_comp_or_group
                   })
    return {"default_text": "Select Tournament", "links": result}

def create_spreadsheet(comp_meta, boxes_config):
    import xlsxwriter
    from django.contrib.staticfiles import finders
    cell_width = 5
    title_row_height = 20
    row_height = 18
    output = StringIO.StringIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    title_format        = workbook.add_format({'align': 'right',  'valign': 'top',     'bold': True,  'border': 0})
    header_format       = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'bold': True,  'border': 2})
    entrant_format      = workbook.add_format({'align': 'left',   'valign': 'vcenter', 'bold': False, 'indent': 0, 'left': 1, 'right': 1})
    last_entrant_format = workbook.add_format({'align': 'left',   'valign': 'vcenter', 'bold': False, 'indent': 0, 'left': 1, 'right': 1, 'bottom': 1})
    worksheet = workbook.add_worksheet("Boxes")
    row = 0
    worksheet.merge_range(row, 0, row, 2*cell_width, "Squash " + comp_meta['name'], title_format)
    worksheet.set_column(0, 2 * cell_width + 1, 5)
    image_path = "images/apple-touch-icon-180x180.png"
    absolute_path = finders.find(image_path)
    if absolute_path is None:
        absolute_path = os.path.join("/usr/local/www", image_path)
    worksheet.insert_image(0, 0, absolute_path, {'positioning': 3, 'x_scale': 0.4, 'y_scale': 0.4})
    row += 3
    for box in boxes_config:
        row_reset = None
        if box['colspec'] == "single":
            col = 1 + cell_width / 2
        elif box['nthcol'] == 'second':
            col = cell_width + 1
        else:
            row_reset = row
            col = 0
        worksheet.set_row(row, title_row_height)
        worksheet.merge_range(row, col, row, col + cell_width-1, box['name'], header_format)
        row += 1
        entrants = box['entrants']
        for (i,e) in enumerate(entrants):
            print e
            worksheet.set_row(row, row_height)
            fmt = (i+1) < len(entrants) and entrant_format or last_entrant_format
            worksheet.merge_range(row, col, row, col + cell_width-1, e.get_players_as_string(), fmt)
            row += 1
        if row_reset is not None:
            row = row_reset
        else:
            row += 1
    workbook.close()
    return output.getvalue()

def create_box_config(previous_cfg, competition, entrants, auth_user_id, is_editor):
    is_second = False
    if previous_cfg is not None:
        if previous_cfg["name"][:-1] == competition.name[:-1]: # e.g. "League 1A" vs "League 1B"
            is_second = True
            previous_cfg["colspec"] = 'double'
            previous_cfg["nthcol"] = 'first'
    def this_user():
        for e in entrants.itervalues():
            if e["player1__user__id"] == auth_user_id:
                return True
        return False
    can_edit = competition.state == "active" and (is_editor or this_user())
    return {"colspec": is_second and "double" or "single",
            "nthcol": is_second and 'second' or 'first',
            "name": competition.name,
            "id": competition.id,
            "can_edit": can_edit,
            }

def enrich_entrants(entrants, matches):
    entrants = dict([(e["id"], e) for e in entrants])
    for e in entrants.values():
        e["Pts"] = 0
    def append(entrant, field, n):
        points = entrant.get(field) or 0
        points += n
        entrant[field] = points            
    for match in matches:
        e1 = entrants[match.team1_id]
        e2 = entrants[match.team2_id]
        scores = match.get_scores()
        points = get_box_league_points(match, scores)
        sets_won = match.get_sets_won(scores)
        def totalize(entrant, idx):
            other_idx = 1 if idx == 0 else 0
            append(entrant, "P", 1)
            if sets_won[idx] > sets_won[other_idx]:
                append(entrant, "W", 1)
            elif sets_won[idx] < sets_won[other_idx]:
                append(entrant, "L", 1)
            else:
                append(entrant, "D", 1)
            for s in scores:
                append(entrant, "F", s[idx])
                append(entrant, "A", s[other_idx])
            append(entrant, "Pts", points[idx])
        totalize(e1, 0)
        totalize(e2, 1)
    return entrants

class BoxesViewBase(TemplateView):

    competition_type = "wsrc_boxes"
    box_table_attrs = {}
    league_table_attrs= {}
    table_body_attrs = None

    def create_entrant_cell(self, entrant, auth_user_id):
        content="{player1__user__first_name} {player1__user__last_name}".format(**entrant)
        attrs={
            "class": "text player",
            "data-player_id":  str(entrant["player1__id"]),
            "data-entrant_id": str(entrant["id"]),
        }
        isHTML=False
        if auth_user_id is not None:
            content = "<a href='{url}?filter-ids={id}'>{content}</a>".format(url=reverse("member_list"), id=entrant["player1__id"], content=content)
            isHTML=True
            if auth_user_id == entrant["player1__user__id"]:
                merge_classes(attrs, "wsrc-currentuser")
        return Cell(content, attrs, isHeader=True, isHTML=isHTML)
        
    def create_box_table(self, competition, n, entrants, matches, auth_user_id):
        entrants = entrants.values()
        entrants.sort(key=itemgetter("ordering"))
        entrant_id_to_index_map = dict([(e["id"], i) for i,e in enumerate(entrants)])
        attrs = {
            "id": "box_table_{id}".format(id=competition.id),
            "data-id": str(competition.id),
            "data-name": competition.name,
        }
        attrs.update(self.box_table_attrs)
        merge_classes(attrs, "boxes boxtable ui-table")
        table = Table(n+3, n+1, attrs)
        table.addCell(SpanningCell(2, 1, "", {"class": "noborder"}), 0, 0)
        for i in range(0, n):
            table.addCell(Cell(content=i+1, attrs={"class": "inverse"}, isHeader=True), i+2, 0)
            table.addCell(Cell(content=i+1, attrs={"class": "inverse"}, isHeader=True), 1,   i+1)
            table.addCell(Cell(content="", attrs={"class": "inverse"}, isHeader=True),  i+2, i+1)
        table.addCell(Cell("<span>&Sigma;</span>", attrs={"class": "inverse"}, isHTML=True) , n+2, 0)
        for i, entrant in enumerate(entrants):
            cell = self.create_entrant_cell(entrant, auth_user_id)
            table.addCell(cell, 0, i+1)
        for i in range(len(entrants), n):
            table.addCell(Cell("", {"class": "noborder"}, isHeader=True), 0, i+1)
        attrs = {"class": "number"}
        for match in matches:
            p1 = entrant_id_to_index_map[match.team1_id]
            p2 = entrant_id_to_index_map[match.team2_id]
            points = get_box_league_points(match)
            table.addCell(Cell(points[0], attrs), p2+2, p1+1)
            table.addCell(Cell(points[1], attrs), p1+2, p2+1)
        for i, entrant in enumerate(entrants):
            table.addCell(Cell(entrant.get("Pts") or 0, {"class": "points"}), n+2, i+1) 
        return table.toHtmlString(self.get_table_head(competition), self.table_body_attrs)
    
    def create_league_table(self, competition, entrants, auth_user_id):
        entrants = entrants.values()
        entrants.sort(key=itemgetter("Pts"), reverse=True)        
        attrs = {
            "data-id": str(competition.id),
            "data-name": competition.name,
        }
        attrs.update(self.league_table_attrs)
        merge_classes(attrs, "boxes leaguetable ui-table")

        fields = ["P", "W", "D", "L", "F", "A", "Pts"]
        table = Table(len(fields)+1, len(entrants)+1, attrs)
        table.addCell(Cell("", {"class": "noborder"}), 0, 0)
        for i,field in enumerate(fields):
            table.addCell(Cell(field, attrs={"class": "inverse"}, isHeader=True) , i+1, 0)
        attrs = {}
        for i, entrant in enumerate(entrants):
            cell = self.create_entrant_cell(entrant, auth_user_id)
            table.addCell(cell, 0, i+1)
            for j,field in enumerate(fields):
                cls = "number points" if field == "Pts" else "number"
                attrs["class"] = cls
                table.addCell(Cell(entrant.get(field) or 0, attrs), j+1, i+1)
        return table.toHtmlString(self.get_table_head(competition), self.table_body_attrs)
    
    def get_table_head(self, comp):
        return None
    
    def get_competition_group(self, end_date=None):
        group_queryset = CompetitionGroup.objects.filter(comp_type=self.competition_type).exclude(competition__state="not_started").order_by('-end_date')
        if end_date is None:
            group = group_queryset[0]
        else:
            end_date = parse_iso_date_to_naive(end_date)
            group = get_object_or_404(group_queryset, end_date=end_date)
        return (group, group_queryset)

    def add_selector(self, ctx, groups, selected_group):
        leagues = []
        for group in groups:
            leagues.append({"year": group.end_date.year, 
                            "end_date": group.end_date, 
                            "name": group.name,
                            "link": reverse("boxes") + "/" + group.end_date.isoformat(),
                            "selected": group == selected_group
                        })
        ctx["selector"] =  {"default_text": "Leagues Ending", "links": leagues}
    
    def get_context_data(self, **kwargs):
        (group, possible_groups) = self.get_competition_group(*self.args)
        context = {
            "competition": {"name": group.name, "id": group.id}
        }
        
        is_editor = self.request.user.has_perm("competitions.change_match")
        auth_user_id = self.request.user.id
        context["boxes"] = boxes = []
        max_players = 0
        previous_cfg = None
        all_matches = [m for m in Match.objects.filter(competition__group=group)]
        fields = ["id", "player1__id", "player1__user__id", "player1__user__first_name", "player1__user__last_name", "handicap", "ordering", "competition_id"]
        all_entrants = [p for p in Entrant.objects.filter(competition__group=group).values(*fields)]
        all_leagues = [c for c in group.competition_set.all()]
        for comp in all_leagues:
            matches = [m for m in all_matches if m.competition_id==comp.id]
            entrants = [e for e in all_entrants if e['competition_id']==comp.id]
            entrants = enrich_entrants(entrants, matches)
            max_players = max(max_players, len(entrants))
            cfg = create_box_config(previous_cfg, comp, entrants, auth_user_id, is_editor)
            cfg["competition"] = comp
            cfg["entrants"] = entrants
            cfg["matches"] = matches
            boxes.append(cfg)
            previous_cfg = cfg
        for box in boxes:
            box["box_table"]    = self.create_box_table(box["competition"], max_players, box["entrants"], box["matches"], auth_user_id)
            box["league_table"] = self.create_league_table(box["competition"], box["entrants"], auth_user_id)
            
        self.add_selector(context, possible_groups, group)
        return context

class BoxesUserView(BoxesViewBase):
    template_name = "boxes.html"
    league_table_attrs = {"style": "display: none;"}

    def get_context_data(self, **kwargs):
        context = super(BoxesUserView, self).get_context_data(**kwargs)
        for box in context["boxes"]:
            def serialize(m):
                data = MatchSerializer(m).data
                scores = m.get_scores()
                data["scores"] = scores
                data["points"] = get_box_league_points(m, scores)
                return data
            matches_data = [serialize(m) for m in box["matches"]]
            box["matches_data"] = JSON_RENDERER.render(matches_data)
        return context

class BoxesAdminView(BoxesViewBase):    
    template_name = "boxes_admin.html"
    box_table_attrs = {"class": " ui-helper-hidden"}
    table_body_attrs = {"class": "ui-widget-content"}

    def get(self, request, *args, **kwargs):
        if (request.user.groups.filter(name="Competition Editor").count() == 0 and not request.user.is_superuser):
            raise PermissionDenied()
        return super(BoxesAdminView, self).get(request, *args, **kwargs)


    def get_table_head(self, comp):
        return "<caption class='ui-widget-header'>{comp.name}<button class='small auto'>Auto-Populate</button></caption>".format(**locals())

    def create_entrant_cell(self, entrant, auth_user_id):
        cell = super(BoxesAdminView, self).create_entrant_cell(entrant, None)
        cell.content += " [{id}]".format(id=entrant["player1__id"])
        return cell

    def get_context_data(self, **kwargs):
        context = super(BoxesAdminView, self).get_context_data(**kwargs)
        context['player_data'] = JSON_RENDERER.render(Player.objects.all().values("id", "user__first_name", "user__last_name"))
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
        context['new_boxes'] = [create_new_box_config(i) for i in range(0,21)]
        return context
    

# TODO: create spreadsheet view
    # if request.GET.get('format') == 'xlsx':
    #     payload = create_spreadsheet(comp_meta, boxes)
    #     content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    #     response = HttpResponse(payload, content_type=content_type)
    #     response['Content-Disposition'] = 'attachment; filename="boxes_{date:%Y-%m-%d}.xlsx"'.format(date=group.end_date)
    #     return response


def bracket_view(request, year, name, template_name="tournaments.html"):
    if year is None:
        groups = CompetitionGroup.objects.filter(comp_type='wsrc_tournaments').filter(active=True).order_by("-end_date")
        group = groups[0]
    else:
        group = get_object_or_404(CompetitionGroup.objects, end_date__year=year, comp_type='wsrc_tournaments')

    name = name.replace("_", " ")        
    competition = get_object_or_404(group.competition_set, name__iexact=name)

    bracket_data = JSON_RENDERER.render(CompetitionSerializer(competition, context={"request": FAKE_REQUEST_CONTEXT}).data)
    html_table = tournament.render_tournament(competition)

    ctx = {
        "competition": competition, 
        "bracket": html_table, 
        "bracket_data": bracket_data,
        "is_editor": request.user.is_authenticated and request.user.has_perm("competitions.change_match")
    }
    options = set_view_options(request, ctx)
    ctx["selector"] = get_tournament_links(options, competition)

    return TemplateResponse(request, template_name, ctx)

def squashlevels_upload_view(request):
    cutoff_date = datetime.date.today() - datetime.timedelta(days=30*3)
    groups = CompetitionGroup.objects.filter(comp_type='wsrc_boxes').filter(end_date__gt=cutoff_date)
    matches = []
    for group in groups.all():
        for competition in group.competition_set.all():
            for match in competition.match_set.all():
                matches.append(match)
    return TemplateResponse(request, context={"matches": matches}, template="squashlevels_upload.csv", content_type='text/csv')

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


# Admin REST API views:

class CompetitionEditorPermissionedAPIView(APIView):
    "Restrict update views to competition editors"
    queryset = CompetitionGroup.objects.none() # Required for DjangoModelPermissions
    authentication_classes = (SessionAuthentication,)
    permission_classes = (rest_permissions.IsAuthenticated,rest_permissions.DjangoModelPermissions,)

class SetCompetitionGroupLive(CompetitionEditorPermissionedAPIView):
    parser_classes = (JSONParser,)
    def put(self, request, format="json"):
        competition_group_id = request.data.pop('competition_group_id')
        competition_type = request.data.pop('competition_type')
        new_group = CompetitionGroup.objects.get(pk = competition_group_id)
        old_groups = CompetitionGroup.objects.filter(active = True).filter(comp_type = competition_type)
        for group in old_groups:
            for comp in group.competition_set.all():
                comp.state = "complete"
                comp.save()
            group.active = False
            group.save()
        for comp in new_group.competition_set.all():
            comp.state = "active"
            comp.save()
        new_group.active = True
        new_group.save()
        serialiser = CompetitionGroupSerializer(new_group, context={"request": FAKE_REQUEST_CONTEXT})
        return Response(serialiser.data, status=rest_framework.status.HTTP_201_CREATED)

class SendCompetitionEmail(CompetitionEditorPermissionedAPIView):
    parser_classes = (JSONParser,)
    def put(self, request, format="json"):
        competition_id = request.data.pop('competition_id')
        template_name  = request.data.pop('template_name')
        subject        = request.data.pop('subject')
        from_address   = request.data.pop('from_address')

        competition = Competition.objects.get(pk=competition_id)
        to_list = [entrant.player1.user.email for entrant in competition.entrant_set.all()]
        email_template = EmailContent.objects.get(name=template_name)
        email_template = Template(email_template.markup)
        
        context = Context({"competition": competition})
        context["content_type"] = "text/html"
        html_body = markdown.markdown(email_template.render(context))
        context["content_type"] = "text/plain"
        text_body = email_template.render(context)
    
        email_utils.send_email(subject, text_body, html_body, from_address, to_list)
        return HttpResponse(status=204)

class UpdateTournament(CompetitionEditorPermissionedAPIView):
    parser_classes = (JSONParser,)
    def put(self, request, pk, format="json"):
        comp_id = int(pk)
        comp_data = request.data
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

# Local Variables:
# mode: python
# python-indent-offset: 4
