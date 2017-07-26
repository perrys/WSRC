from django import forms
from django.db import models

from django.contrib import admin
from wsrc.site.models import PageContent, EmailContent, EventFilter, MaintenanceIssue, Suggestion, ClubEvent, CommitteeMeetingMinutes, BookingOffence

class PageContentAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 30})},
    }

class EmailContentAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 30})},
    }

class ClubEventAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 20})},
    }

class CommitteeMeetingMinutesAdmin(admin.ModelAdmin):
    list_display = ("date",)
    formfield_overrides = {
        models.FileField: {'widget': forms.widgets.ClearableFileInput(attrs={'accept':'.pdf'})},
    }

class NotifierEventAdmin(admin.ModelAdmin):
    pass

class MaintenanceIssueAdmin(admin.ModelAdmin):
    list_display = ("description", "reporter", "reported_date", "status",)
    list_filter = ('status',)
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 5})},
    }

class SuggestionAdmin(admin.ModelAdmin):
    list_display = ("description", "suggester", "submitted_date")
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 5})},
    }

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
    
class BookingOffenceAdmin(admin.ModelAdmin):
    list_display = ("player", "entry_id", "offence", "start_time", "creation_time", "cancellation_time", "rebooked", "penalty_points")
    list_editable = ("penalty_points",)
    list_filter = (OffendersListFilter,)
    date_hierarchy = "start_time"
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 5})},
    }



admin.site.register(PageContent, PageContentAdmin)
admin.site.register(EmailContent, EmailContentAdmin)
admin.site.register(EventFilter, NotifierEventAdmin)
admin.site.register(MaintenanceIssue, MaintenanceIssueAdmin)
admin.site.register(Suggestion, SuggestionAdmin)
admin.site.register(ClubEvent, ClubEventAdmin)
admin.site.register(CommitteeMeetingMinutes, CommitteeMeetingMinutesAdmin)
admin.site.register(BookingOffence, BookingOffenceAdmin)
