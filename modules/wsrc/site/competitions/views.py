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

import csv
import re

from django.db.models import Q

from .forms import MatchScoresForm
from wsrc.site.models import EmailContent
from wsrc.site.usermodel.models import Player
from wsrc.site.competitions.models import Competition, CompetitionGroup, Match, Entrant
from wsrc.site.competitions.serializers import CompetitionSerializer, CompetitionGroupSerializer, MatchSerializer, EntrantSerializer
from wsrc.utils.html_table import Table, Cell, SpanningCell, merge_classes
from wsrc.utils.markdown_utils import RedactedLinkExtension
from wsrc.utils.text import obfuscate
from wsrc.utils.timezones import parse_iso_date_to_naive
from wsrc.utils.sync_utils import dotted_lookup
from wsrc.utils import email_utils


from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.template import Template, Context
from django.template.response import TemplateResponse
from django.forms import ModelForm, ModelChoiceField
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView, View
from django.views.generic.edit import UpdateView, CreateView
from django.utils.decorators import method_decorator

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
from . import tournament
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
        if request.user.is_superuser:
            return True
        elif request.method == "GET" \
             or request.method == "PUT" \
             or request.method == "POST" \
             or request.method == "PATCH":
            if request.user.has_perm("competitions.change_match"):
                return True
        elif request.method == "DELETE":
            if request.user.has_perm("competitions.delete_match"):
                return True
        player = get_object_or_404(Player.objects.all(), user=request.user)
        entrants = []
        if hasattr(view, "object"):
            match = view.object
            if match is None: # new match
                return True
            entrants = [match.team1, match.team2]
            for entrant in entrants:
                if entrant.player1 == player or entrant.player2 == player:
                    return True
        else:
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
        if match.competition.group.competition_type.is_knockout_comp:
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
    for group in qset.filter(competition_type__id__icontains="tournament").prefetch_related("competition_set"):
        year = group.end_date.year
        year_suffix = no_navigation and " {year}".format(**locals()) or ""
        comps = [comp for comp in group.competition_set.all() if comp.state != "not_started"]
        comps.sort(key=lambda x: x.name)
        for comp in comps:
            name = comp.name
            result.append({"year": year,
                           "name": name + year_suffix,
                           "end_date": comp.end_date,
                           "link": reverse(bracket_view) + "/{year}/{name}/{suffix}".format(**locals()),
                           "selected": no_navigation and comp == selected_comp_or_group
                       })
    for group in qset.filter(competition_type="tournament_qualifiers", active=True):
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

class BoxesViewBase(object):

    @staticmethod
    def create_box_config(previous_cfg, competition, entrants, auth_user_id, is_editor):
        is_second = False
        if previous_cfg is not None:
            if previous_cfg["name"][:-1] == competition.name[:-1]: # e.g. "League 1A" vs "League 1B"
                is_second = True
                previous_cfg["colspec"] = 'double'
                previous_cfg["nthcol"] = 'first'
        def this_user():
            for e in entrants:
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

    @staticmethod
    def get_all_entrants(comp_group, show_names=False):
        fields = ["id", "player1__id", "player1__user__id", "player1__user__first_name", "player1__user__last_name", "player1__user__is_active", "handicap", "ordering", "competition_id"]
        entrants = [p for p in Entrant.objects.filter(competition__group=comp_group).order_by('ordering').values(*fields)]
        for e in entrants:
            if not show_names:
                for idx, key in enumerate(["player1__user__first_name", "player1__user__last_name"]):
                    e[key] = obfuscate(e[key], to_initial=(idx==0))
            e["full_name"] = " ".join([e["player1__user__first_name"], e["player1__user__last_name"]])
        return entrants

    def get_competition_group(self, comp_type, end_date=None, group_id=None):
        group_queryset = CompetitionGroup.objects.filter(competition_type=comp_type).exclude(competition__state="not_started").order_by('-end_date')
        if end_date is None:
            group = group_queryset[0] if group_queryset.exists() else None
        else:
            end_date = parse_iso_date_to_naive(end_date)
            group = get_object_or_404(group_queryset, end_date=end_date)
        return (group, group_queryset)


class BoxesExcelView(BoxesViewBase, View):

    @staticmethod
    def create_spreadsheet(comp_group, boxes_config):
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
        worksheet.merge_range(row, 0, row, 2*cell_width, "Squash " + comp_group.name, title_format)
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
                worksheet.set_row(row, row_height)
                fmt = (i+1) < len(entrants) and entrant_format or last_entrant_format
                worksheet.merge_range(row, col, row, col + cell_width-1, "{full_name}".format(**e), fmt)
                row += 1
            if row_reset is not None:
                row = row_reset
            else:
                row += 1
        workbook.close()
        return output.getvalue()

    def get(self, request, *args, **kwargs):
        (group, possible_groups) = self.get_competition_group(*args)
        boxes = []
        max_players = 0
        previous_cfg = None
        all_entrants = self.get_all_entrants(group, request.user.is_authenticated())
        all_leagues = [c for c in group.competition_set.all()]
        for comp in all_leagues:
            entrants = [e for e in all_entrants if e['competition_id']==comp.id]
            max_players = max(max_players, len(entrants))
            cfg = self.create_box_config(previous_cfg, comp, entrants, None, None)
            cfg["competition"] = comp
            cfg["entrants"] = entrants
            boxes.append(cfg)
            previous_cfg = cfg
        payload = self.create_spreadsheet(group, boxes)
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response = HttpResponse(payload, content_type=content_type)
        response['Content-Disposition'] = 'attachment; filename="boxes_{date:%Y-%m-%d}.xlsx"'.format(date=group.end_date)
        return response

class BoxesTemplateViewBase(BoxesViewBase, TemplateView):

    box_table_attrs = {}
    league_table_attrs= {}
    table_body_attrs = None

    @staticmethod
    def enrich_entrants(entrants, matches):
        entrants = dict([(e["id"], e) for e in entrants])
        for e in entrants.values():
            e["Pts"] = e["P"] = e["F"] = e["A"] = 0
        def append(entrant, field, n):
            points = entrant.get(field) or 0
            points += n
            entrant[field] = points
        for match in matches:
            e1 = entrants[match.team1_id]
            e2 = entrants[match.team2_id]
            scores = match.get_scores()
            points = match.get_box_league_points(scores)
            winner = match.get_winner(scores, True)
            def totalize(entrant, other_entrant, idx):
                other_idx = 1 if idx == 0 else 0
                append(entrant, "P", 1)
                if entrant["id"] == winner:
                    append(entrant, "W", 1)
                elif other_entrant["id"] == winner:
                    append(entrant, "L", 1)
                else:
                    append(entrant, "D", 1)
                for s in scores:
                    append(entrant, "F", s[idx])
                    append(entrant, "A", s[other_idx])
                append(entrant, "Pts", points[idx])
            totalize(e1, e2, 0)
            totalize(e2, e1, 1)
        return entrants

    @staticmethod
    def sort_entrants(entrants, matches):
        def cmp_head_to_head_match(lhs, rhs):
            matched_match = None
            for match in matches:
                if match.team1_id == lhs["id"] and match.team2_id == rhs["id"] or\
                   match.team2_id == lhs["id"] and match.team1_id == rhs["id"]:
                    matched_match = match
                    break
            if matched_match is None:
                return 0
            winner_id = matched_match.get_winner(key_only=True)            
            if winner_id == lhs["id"]:
                return 1
            if winner_id == rhs["id"]:
                return -1
            return 0
                
        entrants = list(entrants)
        def fair_compare(lhs, rhs):
            diff = lhs["Pts"] - rhs["Pts"]
            if diff == 0:
                diff = cmp_head_to_head_match(lhs, rhs)
            if diff == 0:
                diff = lhs["P"] - rhs["P"]
            if diff == 0:
                diff = (lhs["F"] - lhs["A"]) - (rhs["F"] - rhs["A"])
            if diff == 0:
                diff = -1 * cmp(lhs["player1__user__last_name"],  rhs["player1__user__last_name"])
            if diff == 0:
                diff = -1 * cmp(lhs["player1__user__first_name"],  rhs["player1__user__first_name"])
            return int(diff)
                
        entrants.sort(cmp=fair_compare, reverse=True)
        return entrants
    
    def create_entrant_cell(self, entrant, auth_user_id):
        cls = "" if entrant["player1__user__is_active"] else "inactive"
        content=u"<span class='{cls}'>{full_name}</span>".format(full_name=entrant["full_name"], cls=cls)
        attrs={
            "class": "text player",
            "data-player_id":  str(entrant["player1__id"]),
            "data-entrant_id": str(entrant["id"]),
        }
        if auth_user_id is not None:
            content = u"<a href='{url}?filter-ids={id}'>{content}</a>".format(url=reverse("member_list"), id=entrant["player1__id"], content=content)
            if auth_user_id == entrant["player1__user__id"]:
                merge_classes(attrs, "wsrc-currentuser")
        return Cell(content, attrs, isHeader=True, isHTML=True)

    def create_box_table(self, competition, n, entrants, matches, auth_user_id):
        entrants = list(entrants)
        entrants.sort(key=itemgetter("ordering"))
        entrant_id_to_index_map = dict([(e["id"], i) for i,e in enumerate(entrants)])
        attrs = {
            "id": "box_table_{id}".format(id=competition.id),
            "data-id": str(competition.id),
            "data-name": competition.name,
        }
        attrs.update(self.box_table_attrs)
        merge_classes(attrs, "boxes table")
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
            table.addCell(Cell("", {"class": "player"}, isHeader=True), 0, i+1)
        attrs = {"class": "number"}
        for match in matches:
            p1 = entrant_id_to_index_map[match.team1_id]
            p2 = entrant_id_to_index_map[match.team2_id]
            points = match.get_box_league_points()
            table.addCell(Cell(points[0], attrs), p2+2, p1+1)
            table.addCell(Cell(points[1], attrs), p1+2, p2+1)
        for i, entrant in enumerate(entrants):
            table.addCell(Cell(entrant.get("Pts") or 0, {"class": "points"}), n+2, i+1)
        return table.toHtmlString(self.get_table_head(competition), self.table_body_attrs)

    def create_league_table(self, competition, entrants, auth_user_id):
        attrs = {
            "data-id": str(competition.id),
            "data-name": competition.name,
        }
        attrs.update(self.league_table_attrs)
        merge_classes(attrs, "leagues table")

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

    def add_selector(self, ctx, groups, selected_group):
        leagues = []
        for group in groups:
            leagues.append({"year": group.end_date.year,
                            "end_date": group.end_date,
                            "name": group.name,
                            "id": group.id,
                            "link": reverse(self.reverse_url_name, kwargs={'comp_type': group.competition_type_id}) + "/" + group.end_date.isoformat(),
                            "selected": group == selected_group
                        })
        ctx["selector"] =  {"default_text": "Leagues Ending", "links": leagues}

    def get_context_data(self, **kwargs):
        (most_recent_group, possible_groups) = self.get_competition_group(*self.args, **kwargs)
        if most_recent_group is not None:
            context = {
                "competition": {"name": most_recent_group.name, "id": most_recent_group.id, "type": most_recent_group.competition_type_id}
            }
        else:
            context = {
                "competition": {"type": kwargs["comp_type"]}
            }
            

        is_editor = self.request.user.has_perm("competitions.change_match")
        auth_user_id = self.request.user.id
        context["boxes"] = boxes = []
        max_players = 0
        previous_cfg = None
        all_matches = Match.objects.filter(competition__group=most_recent_group).select_related("team1__player1__user", "team2__player1__user")
        all_matches = [m.cache_scores() for m in all_matches]
        all_entrants = self.get_all_entrants(most_recent_group, self.request.user.is_authenticated())
        all_leagues = []
        if most_recent_group is not None:
            all_leagues = [c for c in most_recent_group.competition_set.all()] 
        for comp in all_leagues:
            matches = [m for m in all_matches if m.competition_id==comp.id]
            entrants = [e for e in all_entrants if e['competition_id']==comp.id]
            self.enrich_entrants(entrants, matches)
            sorted_entrants = self.sort_entrants(entrants, matches)
            max_players = max(max_players, len(entrants))
            cfg = self.create_box_config(previous_cfg, comp, entrants, auth_user_id, is_editor)
            cfg["competition"] = comp
            cfg["entrants"] = entrants
            cfg["sorted_entrants"] = sorted_entrants
            cfg["matches"] = matches
            boxes.append(cfg)
            previous_cfg = cfg
        for box in boxes:
            if "no_navigation" in self.request.GET: # remove player links from this table
                auth_user_id = None
            box["box_table"]    = self.create_box_table(box["competition"], max_players, box["entrants"], box["matches"], auth_user_id)
            box["league_table"] = self.create_league_table(box["competition"], box["sorted_entrants"], auth_user_id)

        self.add_selector(context, possible_groups, most_recent_group)
        return context

class BoxesUserView(BoxesTemplateViewBase):
    template_name = "boxes.html"
    league_table_attrs = {}
    reverse_url_name = "boxes"

    def get_context_data(self, **kwargs):
        context = super(BoxesUserView, self).get_context_data(**kwargs)
        set_view_options(self.request, context)
        if "no_navigation" in context["options"]:
            del context["selector"]
        context["view_type"] = self.request.GET.get("view") or "boxes"
        return context

class BoxesPreviewView(BoxesUserView):
    def get_competition_group(self, comp_type, group_id):
        (group, possible_groups) = super(BoxesPreviewView, self).get_competition_group(comp_type)
        group = get_object_or_404(CompetitionGroup.objects.filter(competition_type=comp_type), pk=group_id)
        return (group, possible_groups)

class BoxesAdminView(BoxesTemplateViewBase):
    template_name = "boxes_admin.html"
    box_table_attrs = {"class": " ui-helper-hidden"}
    table_body_attrs = {"class": "ui-widget-content"}
    reverse_url_name = "boxes_admin"

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
        player_data = Player.objects.all().values("id", "user__first_name", "user__last_name", "user__is_active")
        for p in player_data:
            p["full_name"] = u"{user__first_name} {user__last_name}".format(**p)
        context['player_data'] = JSON_RENDERER.render(dict([(p["id"], p) for p in player_data]))

        # add any unstarted competition
        comp_type = kwargs["comp_type"]
        group_queryset = CompetitionGroup.objects.filter(competition_type=comp_type, competition__state="not_started").order_by('-end_date')
        all_entrants = all_leagues = None
        if group_queryset.count() > 0:
            group = group_queryset[0]
            all_entrants = self.get_all_entrants(group, self.request.user.is_authenticated())
            all_leagues = [c for c in group.competition_set.all()]
            context["new_competition_group"] = group

        def create_new_box_config(idx):
            result = {"id": None, "players": None}
            if idx == 0:
                prefix = "RB" if "squash57" in comp_type else ""
                result["colspec"] = "single"
                result["name"] = "Premier %(prefix)s" % locals()
                result["nthcol"] = "first"
            else:
                prefix = "RB_" if "squash57" in comp_type else ""
                result["colspec"] = "double"
                suffix = (idx % 2 == 1) and "A" or "B"
                number = (idx+1)/2
                result["name"] = "League %(prefix)s%(number)d%(suffix)s" % locals()
                result["nthcol"] = suffix == "A" and "first" or "second"
            result["entrants"] = entrants = []
            if all_leagues is not None:
                leagues = [l for l in all_leagues if l.name == result["name"]]
                if len(leagues) == 1:
                    result["competition"] = leagues[0]
                    entrants.extend([e for e in all_entrants if e["competition_id"] == leagues[0].id])
            while len(entrants) < 6:
                entrants.append({"id": "", "full_name": ""})
            return result
        context['new_boxes'] = [create_new_box_config(i) for i in range(0,21)]
        return context

@login_required
def bracket_view(request, year, name, template_name="tournaments.html"):
    if year is None:
        groups = CompetitionGroup.objects.filter(competition_type__is_knockout_comp=True).filter(active=True).order_by("-end_date")
        group = groups[0]
    else:
        group = get_object_or_404(CompetitionGroup.objects, end_date__year=year, competition_type__is_knockout_comp=True)

    name = name.replace("_", " ")
    comp_set = Competition.objects.filter(group=group, name__iexact=name)\
                                  .prefetch_related("rounds",\
                                                    "match_set")
    competition = get_object_or_404(comp_set, name__iexact=name)
    html_table = tournament.render_tournament(competition)

    ctx = {
        "competition": competition,
        "bracket": html_table,
        "is_editor": request.user.is_authenticated and request.user.has_perm("competitions.change_match")
    }
    options = set_view_options(request, ctx)
    ctx["selector"] = get_tournament_links(options, competition)

    return TemplateResponse(request, template_name, ctx)

def squashlevels_upload_view(request):
    clause = Q(name__istartswith="Premier") |\
             Q(name__istartswith="League 1") |\
             Q(name__istartswith="League 2")
    comps = Competition.objects.filter(group__competition_type='squash_boxes', state='active').filter(clause)
    matches = Match.objects.filter(competition__in=comps, \
                                   team1__player1__squashlevels_id__isnull=False, \
                                   team2__player1__squashlevels_id__isnull=False)
    matches = matches.select_related("team1__player1__user", "team2__player1__user", \
                                     "team1__player2__user", "team2__player2__user", \
                                     "competition__group")
    fields = [("Date", "last_updated", "{0:%Y-%m-%d}"),
              ("Time", "last_updated", "{0:%H:%M}"),
              ("Player1", "team1.player1.user.get_full_name"),
              ("ID1", "team1.player1.id"),
              ("ESM1", "team1.player1.england_squash_id"),
              ("SquashLevelsID1", "team1.player1.squashlevels_id"),
              ("Club1", "#Woking"),
              ("County1", "#Surrey"),
              ("Country1", "#ENG"),
              ("Category1", "team1.player1.junior_or_senior"),
              ("Player2", "team2.player1.user.get_full_name"),
              ("ID2", "team2.player1.id"),
              ("ESM2", "team2.player1.england_squash_id"),
              ("SquashLevelsID2", "team2.player1.squashlevels_id"),
              ("Club2", "#Woking"),
              ("County2", "#Surrey"),
              ("Country2", "#ENG"),
              ("Category2", "team2.player1.junior_or_senior"),
              ("Results", "get_scores_display"),
              ("Matchtype", "competition.group", "WSRC {0}"),
              ("MatchtypeID", "competition.group.id"),
              ("FixtureID", "id"),
    ]
    def resolve_field(match, field):
        if field[1][0] == '#':
            val = field[1][1:]
        else:
            val = dotted_lookup(match, field[1])
            if len(field) > 2:
                val = field[2].format(val)
        return val
    buf = StringIO.StringIO()
    writer = csv.writer(buf)
    writer.writerow([field[0] for field in fields])
    def writerow(match):
        writer.writerow([resolve_field(match, field) for field in fields])            
    for match in matches:
        writerow(match)
    buf.flush()
    return HttpResponse(buf.getvalue(), content_type='text/csv')

class PermissionedView(View):
    "Borrowed from the Django Rest Framework - check permissions before dispatch"

    def get_permissions(self):
        "Instantiates and returns the list of permissions that this view requires."
        if not hasattr(self, "permission_classes"):
            return []
        return [permission() for permission in self.permission_classes]

    def check_permissions(self, request):
        """
        Check if the request should be permitted.
        Raises an appropriate exception if the request is not permitted.
        """
        for permission in self.get_permissions():
            if not permission.has_permission(request, self):
                raise PermissionDenied()

    def dispatch(self, request, *args, **kwargs):
        self.check_permissions(request)
        return super(PermissionedView, self).dispatch(request, *args, **kwargs)

class MatchEntryViewBase(PermissionedView):
    template_name = 'match_result.html'
    form_class = MatchScoresForm
    competition = None
    entrant_set = None
    permission_classes = (SelfUpdateOrCompetitionEditorPermission,)

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        comp_id = int(self.kwargs.get("comp_id"))
        self.competition = Competition.objects.select_related("group").get(pk=comp_id)
        self.entrant_set = Entrant.objects.select_related("player1__user", "player2__user").filter(competition=self.competition)
        return super(MatchEntryViewBase, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        matches = Match.objects.select_related("competition__group")
        matches = matches.select_related("team1__player1__user", "team2__player1__user", "team1__player2__user", "team2__player2__user", )
        comp_id = self.kwargs.get("comp_id")
        result = matches.filter(competition_id=comp_id)
        return result

    def get_context_data(self, **kwargs):
        context = super(MatchEntryViewBase, self).get_context_data(**kwargs)
        context["competition"] = self.competition
        context["competition_group"] = self.competition.group
        context["is_editor"] = self.request.user.has_perm("competitions.change_match")
        comp_data = CompetitionSerializer(self.competition, expand=True, exclude_entrants=True).data
        entrant_data = EntrantSerializer(self.entrant_set, many=True).data
        entrant_map = dict([(entrant["id"], entrant) for entrant in entrant_data])
        context["competition_data"] = JSON_RENDERER.render(comp_data)
        context["entrants_map_data"] = JSON_RENDERER.render(entrant_map)
        context["back_url"] = self.get_success_url()
        set_view_options(self.request, context)
        agent = self.request.META.get("HTTP_USER_AGENT")
        # Eugh - user agent sniffing. I don't see a better way though..
        horizontal_layout = True
        if agent is not None and "iPad" not in agent:
            for test in ["iPhone", "Android", "Mobile"]:
                if test in agent:
                    horizontal_layout = False
                    break
        context["horizontal_scores"] = horizontal_layout
        return context

    def get_form_kwargs(self):
        result = super(MatchEntryViewBase, self).get_form_kwargs()
        comp_id = self.kwargs.get("comp_id")
        result['comp_id'] = comp_id
        result['is_handicap'] = "handicap" in self.competition.name.lower()
        result['is_kiosk'] = "no_navigation" in self.request.GET
        return result

    def get_success_url(self):
        comp_id = self.kwargs.get("comp_id")
        competition = Competition.objects.select_related("group").get(pk=comp_id)
        date = competition.group.end_date.isoformat()
        url = self.request.path
        if not competition.group.competition_type.is_knockout_comp:
            url = reverse(BoxesUserView.reverse_url_name, kwargs={'comp_type':competition.group.competition_type_id}) + "/" + date
        else:
            url = reverse("tournament", args=(competition.group.end_date.year, competition.name))
        if "no_navigation" in self.request.GET:
            url += "?no_navigation"
        return url

class MatchUpdateView(MatchEntryViewBase, UpdateView):
    context_object_name = "match"
    def get_form_kwargs(self):
        result = super(MatchUpdateView, self).get_form_kwargs()
        result['mode'] = 'update'
        if self.request.POST.get("team1") and self.request.POST.get("team2"):
            result['with_teams'] = True
        return result

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super(MatchUpdateView, self).dispatch(request, *args, **kwargs)

class MatchChooseAndUpdateView(MatchUpdateView):
    "Hybrid view allowing match id to be passed as a POST parameter, rather than as part of the URL"
    context_object_name = "match"    

    def get_form_kwargs(self):
        result = super(MatchUpdateView, self).get_form_kwargs()
        result["initial"]["competition"] = self.competition
        result['mode'] = 'choose_and_update'
        return result

    def get_object(self, queryset=None):
        "Allow match_id to be passed in as a POST parameter"
        if queryset is None:
            queryset = self.get_queryset()
        match_id = self.request.POST.get("match", None)
        if match_id is not None:
            return get_object_or_404(queryset, pk=match_id)
        return None

class MatchCreateView(MatchEntryViewBase, CreateView):
    def get_form_kwargs(self):
        result = super(MatchCreateView, self).get_form_kwargs()
        result["initial"]["competition"] = self.competition
        team1 = None
        for entrant in self.entrant_set:
            for player in [entrant.player1, entrant.player2]:
                if player is not None and player.user == self.request.user:
                    team1 = entrant
                    break
            if team1 is not None:
                result["initial"]["team1"] = team1
                break
        return result
    def dispatch(self, request, *args, **kwargs):
        self.object = None
        return super(MatchCreateView, self).dispatch(request, *args, **kwargs)

@require_GET
def bracket_admin_view(request, year=None, name=None):
    if not request.user.is_authenticated():
        raise PermissionDenied()

    competition = None
    comp_data = '{}'
    comps = Competition.objects.filter(group__competition_type__is_knockout_comp=True).select_related("group")\
                                                                           .prefetch_related("entrant_set__player1__user", \
                                                                           "entrant_set__player2__user")
    if name is not None:
        name = name.replace("_", " ")
        competition = get_object_or_404(comps, name__iexact=name, group__end_date__year=year)
        comp_data = JSON_RENDERER.render(CompetitionSerializer(competition, context={"request": FAKE_REQUEST_CONTEXT}).data)

    
    tournaments = dict()
    for comp in comps:
        comp_list_for_year = tournaments.setdefault(comp.group.end_date.year, [])
        comp_list_for_year.append(comp)
    tournaments = [{"year": key, "competitions": value} for (key, value) in tournaments.items()]

    return render(request, 'tournaments_admin.html', {
        'selected_competition': competition,
        'players':              Player.objects.filter(user__is_active=True).select_related("user"),
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
        new_group = CompetitionGroup.objects.get(pk = competition_group_id)
        old_groups = CompetitionGroup.objects.filter(active = True).filter(competition_type = new_group.competition_type)
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
        to_list = []
        bcc_list = []
        for entrant in competition.entrant_set.all():
            email = entrant.player1.user.email
            if entrant.player1.prefs_display_contact_details:
                to_list.append(email)
            else:
                bcc_list.append(email)
        email_template = EmailContent.objects.get(name=template_name)
        email_template = Template(email_template.markup)

        context = Context({"competition": competition, "has_redacted": len(bcc_list) > 0})
        context["content_type"] = "text/html"
        extensions = ['markdown.extensions.extra', 'markdown.extensions.smarty', RedactedLinkExtension()]
        html_body = markdown.markdown(email_template.render(context), extensions=extensions)
        context["content_type"] = "text/plain"
        text_body = email_template.render(context)

        email_utils.send_email(subject, text_body, html_body, from_address, to_list, bcc_list=bcc_list)
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
