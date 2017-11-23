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

"Admin for the general site models"

from django import forms
from django.db import models

from django.contrib import admin
from wsrc.site.models import PageContent, EmailContent, EventFilter, MaintenanceIssue,\
    Suggestion, ClubEvent, CommitteeMeetingMinutes, GenericPDFDocument, Image
from wsrc.utils.form_utils import PrefetchRelatedQuerysetMixin

def txt_widget(nrows):
    "Create a standard textarea widget"
    return forms.Textarea(attrs={'cols': 100, 'rows': nrows})

class PageContentAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': txt_widget(30)},
    }

class EmailContentAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': txt_widget(30)},
    }

class ClubEventAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': txt_widget(20)},
    }

class PDFFileAdmin(admin.ModelAdmin):
    list_display = ("date", "get_link")
    formfield_overrides = {
        models.FileField: {'widget': forms.widgets.ClearableFileInput(attrs={'accept':'.pdf'})},
    }
    def get_link(self, obj, link_text=None):
        if link_text is None:
            link_text = obj.get_url()
        return "<a href='{url}' style='font-weight: bold'>{text}</a>".format(url=obj.get_url(), text=link_text)
    get_link.short_description = "Link"
    get_link.allow_tags = True

class ImageAdmin(admin.ModelAdmin):
    list_display = ("date", "get_link", "width", "height")
    formfield_overrides = {
        models.FileField: {'widget': forms.widgets.ClearableFileInput(attrs={'accept':'.jpg,.jpeg,.JPG,.gif,.GIF,.png'})},
    }
    def get_link(self, obj, link_text=None):
        if link_text is None:
            link_text = obj.image_file.url
        return "<a href='{url}' style='font-weight: bold'>{text}</a>".format(url=obj.image_file.url, text=link_text)
    get_link.short_description = "Link"
    get_link.allow_tags = True

class NotifierEventAdmin(PrefetchRelatedQuerysetMixin, admin.ModelAdmin):
    list_select_related = ('player__user',)
    prefetch_related_fields = ('days',)

class MaintenanceIssueAdmin(admin.ModelAdmin):
    list_display = ("description", "reporter", "reported_date", "status",)
    list_filter = ('status',)
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 5})},
    }
    list_select_related = ('reporter__user',)

class SuggestionAdmin(admin.ModelAdmin):
    list_display = ("description", "suggester", "submitted_date")
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 5})},
    }
    list_select_related = ('suggester__user',)


admin.site.register(PageContent, PageContentAdmin)
admin.site.register(EmailContent, EmailContentAdmin)
admin.site.register(EventFilter, NotifierEventAdmin)
admin.site.register(MaintenanceIssue, MaintenanceIssueAdmin)
admin.site.register(Suggestion, SuggestionAdmin)
admin.site.register(ClubEvent, ClubEventAdmin)
admin.site.register(CommitteeMeetingMinutes, PDFFileAdmin)
admin.site.register(GenericPDFDocument, PDFFileAdmin)
admin.site.register(Image, ImageAdmin)
