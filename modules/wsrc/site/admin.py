from django import forms
from django.db import models

from django.contrib import admin
from wsrc.site.models import PageContent, EmailContent, EventFilter

class PageContentAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 40})},
    }

class EmailContentAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 40})},
    }

class NotifierEventAdmin(admin.ModelAdmin):
    pass


admin.site.register(PageContent, PageContentAdmin)
admin.site.register(EmailContent, EmailContentAdmin)
admin.site.register(EventFilter, NotifierEventAdmin)
