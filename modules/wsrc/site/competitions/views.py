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
from wsrc.site.competitions.serializers import CompetitionSerializer, CompetitionGroupSerializer, MatchSerializer
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
import tournament

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
            for j in (1,2):
                if request.data.get("team%(i)d_player%(j)d" % locals()) == player.id:
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
            winners = match.get_winners()
            if winners is None:
                return HttpResponse("tournament matches must have a winner", status=400)
            tournament.submit_match_winners(match, winners)
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

def get_boxes_links(options, selected_group):
    leagues = []
    no_navigation = "no_navigation" in options
    suffix = no_navigation and "?no_navigation" or ""
    for group in CompetitionGroup.objects.filter(comp_type="wsrc_boxes").exclude(competition__state="not_started"):
        leagues.append({"year": group.end_date.year, 
                        "end_date": group.end_date, 
                        "name": group.name,
                        "link": reverse(boxes_view) + "/" + group.end_date.isoformat() + suffix,
                        "selected": no_navigation and group == selected_group
                    })
    return {"default_text": "Leagues Ending", "links": leagues}

def boxes_view(request, end_date=None, template_name="boxes.html", check_permissions=False, comp_type="boxes", name=None, year=None):
    """Return a view of the Leagues for ending on END_DATE. If
    END_DATE is  negative, the current league is shown"""

    if check_permissions:
        if (request.user.groups.filter(name="Competition Editor").count() == 0 and not request.user.is_superuser):
            raise PermissionDenied()

    queryset = CompetitionGroup.objects.filter(comp_type="wsrc_" + comp_type)
    if end_date is None:
        if year is not None:
            name = "{comp_type} - {name} {year}".format(**locals())
            group = get_object_or_404(queryset, end_date__year=year, name__iexact=name)

        groups = queryset.exclude(competition__state="not_started").order_by('-end_date')
        group = groups[0]
    else:
        end_date = parse_iso_date_to_naive(end_date)
        group = get_object_or_404(queryset, end_date=end_date)

    box_data = JSON_RENDERER.render(CompetitionGroupSerializer(group, context={"request": FAKE_REQUEST_CONTEXT}).data)
    competition_groups = JSON_RENDERER.render(CompetitionGroupSerializer(queryset, many=True).data)
    is_editor = request.user.has_perm("competitions.change_match")

    def create_box_config(previous_comp, competition, ctx):
        is_second = False
        ctx["maxplayers"] = max(ctx["maxplayers"], len(competition.entrant_set.all()))
        if previous_comp is not None:
            if previous_comp["name"][:-1] == competition.name[:-1]: # e.g. "League 1A" vs "League 1B"
                is_second = True
                previous_comp["colspec"] = 'double'
                previous_comp["nthcol"] = 'first'
        entrants = [p for p in competition.entrant_set.all().order_by("ordering")]
        def this_user():
            for e in entrants:
                if e.player.user.id == request.user.id:
                    return True
            return False
        can_edit = is_editor or this_user()
        return {"colspec": is_second and "double" or "single",
                "nthcol": is_second and 'second' or 'first',
                "name": competition.name,
                "id": competition.id,
                "entrants": entrants,
                "can_edit": can_edit,
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
    options = set_view_options(request, ctx)
    for league in group.competition_set.all():
        cfg = create_box_config(last, league, comp_meta)
        boxes.append(cfg)
        last = cfg
        if cfg["nthcol"] == "second":
          last = None
    for box in boxes:
        while len(box["entrants"]) < comp_meta["maxplayers"]:
            box["entrants"].append(nullplayer)
    ctx["boxes"] = boxes
    ctx["new_boxes"] = new_boxes
    ctx["is_editor"] = is_editor
    ctx["competition_groups"] = competition_groups
    ctx["selector"] = comp_type == "boxes" and get_boxes_links(options, group) or get_tournament_links(options, group)
    ctx["box_data"] = box_data
    ctx['players'] = Player.objects.all() # TODO - filter to players in comp group
    return TemplateResponse(request, template_name, ctx)
    

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
        to_list = [entrant.player.user.email for entrant in competition.entrant_set.all()]
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

