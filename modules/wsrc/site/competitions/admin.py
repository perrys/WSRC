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

class CompetitionInline(admin.TabularInline):
    model = comp_models.Competition

class CompetitionGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "comp_type", "end_date", "active",)
    list_filter = ('comp_type',)
    inlines = (CompetitionInline,)
admin.site.register(comp_models.CompetitionGroup, CompetitionGroupAdmin)

class EntrantInline(admin.TabularInline):
    model = comp_models.Entrant

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
admin.site.register(comp_models.Competition, CompetitionAdmin)

class CompetitionRoundAdmin(admin.ModelAdmin):
    list_display = ("competition", "round", "end_date")
admin.site.register(comp_models.CompetitionRound, CompetitionRoundAdmin)

class MatchAdminForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(MatchAdminForm, self).__init__(*args, **kwargs)
        self.fields['team1'].queryset = self.fields['team2'].queryset = comp_models.Entrant.objects.filter(competition=self.instance.competition)

class MatchAdmin(admin.ModelAdmin):
    form = MatchAdminForm
    list_filter = ('competition__group', 'competition__name')
    list_display = ("competition", "team1", "team2", "competition_match_id", "get_scores_display", "walkover", "last_updated")
    list_editable = ("competition_match_id", )
admin.site.register(comp_models.Match, MatchAdmin)

class EntrantAdmin(admin.ModelAdmin):
    list_display = ("competition", "player1", "player2", "ordering", "handicap", "seeded")
    list_filter = ('competition__group', 'competition__name')
    list_editable = ('handicap', 'seeded')

    
admin.site.register(comp_models.Entrant, EntrantAdmin)

