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

from django.contrib import admin

# Register your models here.

import wsrc.site.competitions.models as comp_models

class CompetitionGroupAdmin(admin.ModelAdmin):
    list_display = ("name", "comp_type", "end_date", "active",)
admin.site.register(comp_models.CompetitionGroup, CompetitionGroupAdmin)

class CompetitionAdmin(admin.ModelAdmin):
    list_display = ("name", "group", "state", "end_date")
admin.site.register(comp_models.Competition, CompetitionAdmin)

class CompetitionRoundAdmin(admin.ModelAdmin):
    list_display = ("competition", "round", "end_date")
admin.site.register(comp_models.CompetitionRound, CompetitionRoundAdmin)

class MatchAdmin(admin.ModelAdmin):
    list_display = ("competition", "team1_player1", "team1_player2", "team2_player1", "team2_player2", "last_updated")
admin.site.register(comp_models.Match, MatchAdmin)

class EntrantAdmin(admin.ModelAdmin):
    list_display = ("competition", "player", "player2")
admin.site.register(comp_models.Entrant, EntrantAdmin)

