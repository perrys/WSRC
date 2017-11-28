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

from django import forms
from django.contrib import admin

# Register your models here.

import wsrc.site.competitions.models as comp_models
from wsrc.utils.form_utils import CachingModelChoiceField, get_related_field_limited_queryset

class CompetitionInline(admin.TabularInline):
    model = comp_models.Competition
    def get_queryset(self, request):
        qs = super(CompetitionInline, self).get_queryset(request)
        qs = qs.select_related("group")
        return qs

class CompetitionGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "comp_type", "end_date", "active",)
    list_filter = ('comp_type',)
    inlines = (CompetitionInline,)
admin.site.register(comp_models.CompetitionGroup, CompetitionGroupAdmin)

class EntrantForm(forms.ModelForm):
    "Override subscription form for more efficient DB interaction"
    player_queryset = get_related_field_limited_queryset(comp_models.Entrant.player1.field)\
                      .select_related("user")
    player1 = CachingModelChoiceField(queryset=player_queryset)
    player2 = CachingModelChoiceField(queryset=player_queryset)
    comp_queryset = get_related_field_limited_queryset(comp_models.Entrant.competition.field)\
                      .select_related("group")
    competition = CachingModelChoiceField(queryset=comp_queryset)

class MatchForm(forms.ModelForm):
    "Override form for more efficient DB interaction."
    entrant_queryset = get_related_field_limited_queryset(comp_models.Match.team1.field)\
                      .select_related("player1__user", "player2__user")
    team1 = CachingModelChoiceField(queryset=entrant_queryset)
    team2 = CachingModelChoiceField(queryset=entrant_queryset)
    comp_queryset = get_related_field_limited_queryset(comp_models.Entrant.competition.field)\
                      .select_related("group")
    competition = CachingModelChoiceField(queryset=comp_queryset)
             
class CompetitionRoundForm(forms.ModelForm):
    "Override subscription form for more efficient DB interaction"
    comp_queryset = get_related_field_limited_queryset(comp_models.Entrant.competition.field)\
                      .select_related("group")
    competition = CachingModelChoiceField(queryset=comp_queryset)

    
class EntrantInline(admin.TabularInline):
    model = comp_models.Entrant
    form = EntrantForm
    def get_queryset(self, request):
        qs = super(EntrantInline, self).get_queryset(request)
        qs = qs.select_related("player1__user", "player2__user")
        return qs

class MatchInLine(admin.TabularInline):
    model = comp_models.Match
    form = MatchForm
    def get_queryset(self, request):
        "Override the form's queryset to select related player/user, when displaying original values"
        qs = super(MatchInLine, self).get_queryset(request)
        qs = qs.select_related("team1__player1__user", "team2__player1__user", "team1__player2__user", "team2__player2__user", )
        return qs
    def get_formset(self, request, obj=None, **kwargs):
        "Override the inline Match formset to restrict entrants to this competition's"
        result = super(MatchInLine, self).get_formset(request, obj, **kwargs)
        queryset = obj.entrant_set.select_related("player1__user", "player2__user")
        result.form.base_fields['team1'].queryset = queryset
        result.form.base_fields['team2'].queryset = queryset
        return result

def set_in_progress(modeladmin, request, queryset):
  queryset.update(state="active")
set_in_progress.short_description="Start"
def set_concluded(modeladmin, request, queryset):
  queryset.update(state="complete")
set_concluded.short_description="Conclude"
def set_not_started(modeladmin, request, queryset):
  queryset.update(state="not_started")
set_not_started.short_description="Un-start"

class CompetitionAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "number_of_entrants", "state", "end_date", "ordering", "url")
    list_filter = ('group__comp_type', 'group', 'state')
    inlines = (EntrantInline,MatchInLine,)
    actions=(set_not_started, set_in_progress, set_concluded)
    def get_queryset(self, request):
        qs = super(CompetitionAdmin, self).get_queryset(request)
        qs = qs.select_related('group')
        qs = qs.prefetch_related("entrant_set")
        return qs
    def number_of_entrants(self, obj):
        return len(obj.entrant_set.all())
    number_of_entrants.short_description = "# Entrants"
    
    
    
admin.site.register(comp_models.Competition, CompetitionAdmin)


class CompetitionRoundAdmin(admin.ModelAdmin):
    list_display = ("competition", "round", "end_date")
    form = CompetitionRoundForm
    def get_queryset(self, request):
        qs = super(CompetitionRoundAdmin, self).get_queryset(request)
        qs = qs.select_related('competition', 'competition__group')
        return qs
admin.site.register(comp_models.CompetitionRound, CompetitionRoundAdmin)

class MatchAdminForm(MatchForm):
    def __init__(self, *args, **kwargs):
        # restrict entrant choices to just the set defined for the match's competition
        super(MatchAdminForm, self).__init__(*args, **kwargs)
        self.fields['team1'].queryset = self.fields['team2'].queryset =\
                                        self.instance.competition.entrant_set.select_related()

class MatchAdmin(admin.ModelAdmin):
    form = MatchAdminForm
    list_filter = ('competition__group', 'competition__name')
    list_display = ("competition", "team1", "team2", "competition_match_id", "get_scores_display", "walkover", "last_updated")
    list_editable = ("competition_match_id", )
    def get_queryset(self, request):
        qs = super(MatchAdmin, self).get_queryset(request)
        qs = qs.select_related('competition__group', 'team1__player1__user', 'team1__player2__user', 'team2__player1__user', 'team2__player2__user')
        return qs
admin.site.register(comp_models.Match, MatchAdmin)

class EntrantAdmin(admin.ModelAdmin):
    list_display = ("competition", "player1", "player2", "ordering", "handicap", "seeded")
    list_filter = ('competition__group', 'competition__name')
    list_editable = ('handicap', 'seeded')
    form = EntrantForm
    def get_queryset(self, request):
        qs = super(EntrantAdmin, self).get_queryset(request)
        qs = qs.select_related('competition__group', 'player1__user', 'player2__user')
        return qs    
admin.site.register(comp_models.Entrant, EntrantAdmin)

