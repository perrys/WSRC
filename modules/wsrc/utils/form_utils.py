# -*- coding: utf-8 -*-
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

"General Utilities and widgets for forms"

from __future__ import unicode_literals

from django import forms
from django.utils.encoding import force_text
from django.utils.html import format_html
from django.utils.safestring import mark_safe


class LabeledSelect(forms.Select):
    """Extends Select widget to set a default label attribute on empty options, 
    passing html5 validation"""

    def __init__(self, attrs=None, choices=(), default_label="(None)", disable_default=False):
        super(LabeledSelect, self).__init__(attrs, choices)
        self.default_label = default_label
        self.disable_default = disable_default

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super(LabeledSelect, self).create_option(name, value, label, selected, index, subindex, attrs)
        option_value = option["value"]
        if option_value is not None:
            option_value = force_text(option_value) 
        option_attrs = option["attrs"]
        if option_value is None or len(option_value) == 0:
            option_attrs["label"] = self.default_label
            if self.disable_default:
                option_attrs["disabled"] = True
                option_attrs["hidden"] = True
        return option


def make_readonly_widget():
    return forms.TextInput(attrs={'class': 'readonly', 'readonly': 'readonly', 'style': 'text-align: left'})


def add_formfield_attrs(form):
    for field in form.fields.values():
        if hasattr(field.widget, "input_type"):
            input_type = getattr(field.widget, "input_type")
            if input_type in ["checkbox", "radio"]:
                continue
        classes = field.widget.attrs.get('class')
        if classes:
            field.widget.attrs['class'] = classes + ' form-control'
        else:
            field.widget.attrs['class'] = 'form-control'
    return form


class SelectRelatedForeignFieldMixin(object):
    "Use in a ModelAdmin to ensure that foreign field querysets have select_related()"

    def formfield_for_foreignkey(self, db_field, request=None, **kwargs):
        field = super(SelectRelatedForeignFieldMixin, self).formfield_for_foreignkey(db_field, request, **kwargs)
        field.queryset = field.queryset.select_related()
        field.cache_choices = True
        return field


class SelectRelatedQuerysetMixin(object):
    """Call select_related on result of get_queryset.

       NOTE - if this is used for list admin optimization, consider
       setting list_select_related=True on the admin class instead.
    """

    def get_queryset(self, request):
        queryset = super(SelectRelatedQuerysetMixin, self).get_queryset(request)
        queryset = queryset.select_related()
        return queryset


class PrefetchRelatedQuerysetMixin(object):
    "Call select_related on queryset used for admin list page"

    def get_queryset(self, request):
        queryset = super(PrefetchRelatedQuerysetMixin, self).get_queryset(request)
        queryset = queryset.prefetch_related(*self.prefetch_related_fields)
        return queryset


class CachingModelChoiceIterator(forms.models.ModelChoiceIterator):
    "Avoids requerying the database for the given queryset"

    def __iter__(self):
        if self.field.empty_label is not None:
            yield (u"", self.field.empty_label)
        for obj in self.queryset:  # instead of queryset.all()
            yield self.choice(obj)


class CachingModelChoiceField(forms.ModelChoiceField):
    "ModelChoiceField which substitutes an efficient queryset iterator"

    def _get_choices(self):
        if hasattr(self, '_choices'):
            return self._choices
        return CachingModelChoiceIterator(self)

    choices = property(_get_choices, forms.ModelChoiceField._set_choices)


class CachingModelMultipleChoiceField(CachingModelChoiceField, forms.ModelMultipleChoiceField):
    "ModelMultipleChoiceField which substitutes an efficient queryset iterator"


def get_related_field_limited_queryset(db_field):
    "Get the default queryset for choices for a related field, limited as specified on the model"
    rel_field = db_field.remote_field
    q_filter = rel_field.limit_choices_to
    if q_filter is not None and len(q_filter) > 0:
        return rel_field.model.objects.filter(q_filter)
    return rel_field.model.objects.all()
