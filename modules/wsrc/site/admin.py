from django import forms
from django.db import models

from django.contrib import admin
from wsrc.site.models import PageContent

class PageContentAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 40})},
    }

admin.site.register(PageContent, PageContentAdmin)
