from django import forms
from django.db import models

from django.contrib import admin
from wsrc.site.models import PageContent, EmailContent, EventFilter, MaintenanceIssue, Suggestion, ClubEvent, CommitteeMeetingMinutes

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


admin.site.register(PageContent, PageContentAdmin)
admin.site.register(EmailContent, EmailContentAdmin)
admin.site.register(EventFilter, NotifierEventAdmin)
admin.site.register(MaintenanceIssue, MaintenanceIssueAdmin)
admin.site.register(Suggestion, SuggestionAdmin)
admin.site.register(ClubEvent, ClubEventAdmin)
admin.site.register(CommitteeMeetingMinutes, CommitteeMeetingMinutesAdmin)
