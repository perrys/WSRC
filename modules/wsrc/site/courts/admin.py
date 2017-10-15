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
from django.db import models

from django.contrib import admin
from wsrc.site.courts.models import BookingOffence

class OffendersListFilter(admin.SimpleListFilter):
    title = "offender"
    parameter_name = "offender"
    def lookups(self, request, model_admin):
        players = dict()
        for offence in BookingOffence.objects.all():
            players[offence.player.id] = offence.player
        players = players.values()
        players.sort(cmp = lambda x,y: cmp(x.user.get_full_name(), y.user.get_full_name()))
        return [(item.user.username, item.user.get_full_name()) for item in players]
    def queryset(self, request, queryset):
        val = self.value()
        if val is not None:
            queryset = queryset.filter(player__user__username=val)
        return queryset        

def set_inactive(modeladmin, request, queryset):
  queryset.update(is_active=False)
def set_active(modeladmin, request, queryset):
  queryset.update(is_active=True)

class BookingOffenceAdmin(admin.ModelAdmin):
    list_display = ("player", "entry_id", "offence", "start_time", "creation_time", "cancellation_time", "rebooked", "penalty_points", "is_active", "comment")
    list_editable = ("penalty_points", "is_active", "comment")
    list_filter = (OffendersListFilter,)
    date_hierarchy = "start_time"
    actions=(set_inactive, set_active)
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 30, 'rows': 1})},
        models.IntegerField: {'widget': forms.NumberInput(attrs={'style': 'width: 3em;'})},
    }


admin.site.register(BookingOffence, BookingOffenceAdmin)
