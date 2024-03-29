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
from wsrc.site.models import PageContent, EmailContent, MaintenanceIssue,\
    Suggestion, ClubEvent, CommitteeMeetingMinutes, GenericPDFDocument, Image,\
    NavigationLink, NavigationNode, OAuthAccess, LeagueMasterFixtures, SquashLevels,\
    NewsItem

from django.contrib.admin.models import LogEntry
admin.site.register(LogEntry)

from wsrc.utils.form_utils import CachingModelChoiceField, \
    get_related_field_limited_queryset, PrefetchRelatedQuerysetMixin

from wsrc.utils.admin_utils import CSVModelAdmin

def txt_widget(nrows):
    "Create a standard textarea widget"
    return forms.Textarea(attrs={'cols': 100, 'rows': nrows})

class PageContentAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': txt_widget(30)},
    }

class NavigationForm(forms.ModelForm):
    "Override parent node in form for more efficient DB interaction"
    parent = CachingModelChoiceField(queryset=NavigationNode.objects.parent_nodes(), required=False)

class NavigationLinkAdmin(PrefetchRelatedQuerysetMixin, CSVModelAdmin):
    list_display = ("name", "url", "is_reverse_url", "is_restricted", "icon", "parent", "ordering")
    list_editable = ("parent", "ordering",)
    prefetch_related_fields = ("parent",)
    def get_changelist_form(self, request, **kwargs):
        return NavigationForm
    form = NavigationForm

class NavigationNodeAdmin(PrefetchRelatedQuerysetMixin, CSVModelAdmin):
    list_display = ("name", "is_restricted", "icon", "parent", "ordering")
    list_editable = ("ordering",)
    prefetch_related_fields = ("parent",)
    form = NavigationForm

class EmailContentAdmin(admin.ModelAdmin):
    formfield_overrides = {
        models.TextField: {'widget': txt_widget(30)},
    }

class ClubEventAdmin(CSVModelAdmin):
    list_display = ("title", "display_date", "display_time")
    formfield_overrides = {
        models.TextField: {'widget': txt_widget(20)},
    }

class NewsItemAdmin(CSVModelAdmin):
    list_display = ("display_date", "title")
    formfield_overrides = {
        models.TextField: {'widget': txt_widget(20)},
    }

class PDFFileAdmin(CSVModelAdmin):
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

class ImageAdmin(CSVModelAdmin):
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

class MaintenanceIssueAdmin(CSVModelAdmin):
    list_display = ("description", "reporter", "reported_date", "status",)
    list_filter = ('status',)
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 5})},
    }
    list_select_related = ('reporter__user',)

class SuggestionAdmin(CSVModelAdmin):
    list_display = ("description", "suggester", "submitted_date")
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 5})},
    }
    list_select_related = ('suggester__user',)

class OAuthForm(forms.ModelForm):
    "Override parent node in form for more efficient DB interaction"
    temporary_access_code = forms.CharField(required=False)

class OAuthAdmin(CSVModelAdmin):
    list_display = ("name", "grant_type", "client_id", "get_login_link", "access_token")
    list_editable = ("access_token", )
    form = OAuthForm
    def get_login_link(self, obj):
        url = obj.login_link
        if url is not None:
            link_text = "(click to get temp. access code)"
            return "<a href='{url}'>{text}</a>".format(url=url, text=link_text)
        return None
    get_login_link.short_description = "Temp. Access Code Link"
    get_login_link.allow_tags = True

admin.site.register(PageContent, PageContentAdmin)
admin.site.register(NavigationNode, NavigationNodeAdmin)
admin.site.register(NavigationLink, NavigationLinkAdmin)
admin.site.register(EmailContent, EmailContentAdmin)
admin.site.register(MaintenanceIssue, MaintenanceIssueAdmin)
admin.site.register(Suggestion, SuggestionAdmin)
admin.site.register(ClubEvent, ClubEventAdmin)
admin.site.register(NewsItem, NewsItemAdmin)
admin.site.register(CommitteeMeetingMinutes, PDFFileAdmin)
admin.site.register(GenericPDFDocument, PDFFileAdmin)
admin.site.register(Image, ImageAdmin)
admin.site.register(OAuthAccess, OAuthAdmin)

admin.site.register(LeagueMasterFixtures, admin.ModelAdmin) 
admin.site.register(SquashLevels, admin.ModelAdmin) 
