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
    list_display = ("name", "group", "state", "end_date", "ordering", "url")
    list_editable = ("state", "end_date", "ordering", "url")
    list_filter = ('group__comp_type', 'group', 'state')
#    inlines = (EntrantInline,MatchInLine,) # TODO: figure out why inlines seem to really kill the CPU
    inlines = (EntrantInline,)
    actions=(set_not_started, set_in_progress, set_concluded)
    def get_queryset(self, request):
        qs = super(CompetitionAdmin, self).get_queryset(request)
        qs = qs.select_related('group')
        return qs
    
admin.site.register(comp_models.Competition, CompetitionAdmin)


class CompetitionRoundAdmin(admin.ModelAdmin):
    list_display = ("competition", "round", "end_date")
    form = CompetitionRoundForm
    def get_queryset(self, request):
        qs = super(CompetitionRoundAdmin, self).get_queryset(request)
        qs = qs.select_related('competition', 'competition__group')
        return qs
admin.site.register(comp_models.CompetitionRound, CompetitionRoundAdmin)

class MatchAdminForm(forms.ModelForm):
    comp_queryset = get_related_field_limited_queryset(comp_models.Entrant.competition.field)\
                      .select_related("group")
    competition = CachingModelChoiceField(queryset=comp_queryset)
    def __init__(self, *args, **kwargs):
        super(MatchAdminForm, self).__init__(*args, **kwargs)
        self.fields['team1'].queryset = self.fields['team2'].queryset =\
                                        comp_models.Entrant.objects.filter(competition=self.instance.competition).select_related()

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

