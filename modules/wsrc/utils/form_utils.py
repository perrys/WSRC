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

from __future__ import unicode_literals

from django import forms

from django.utils.html import format_html
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe

class LabeledSelect(forms.Select):
  "Extends Select widget to set a default label attribute on empty options, passing html5 validation"
  
  def __init__(self, attrs=None, choices=(), default_label="(None)"):
    super(LabeledSelect, self).__init__(attrs, choices)
    self.default_label = default_label
  def render_option(self, selected_choices, option_value, option_label):
    label_html = ''
    if option_value is None:
      option_value = ''
    option_value = force_text(option_value)
    if option_label is None or len(option_label) == 0:
      label_html = mark_safe(' label="{label}"'.format(label=self.default_label))      
    if option_value in selected_choices:
      selected_html = mark_safe(' selected="selected"')
      if not self.allow_multiple_selected:
        # Only allow for a single selection.
        selected_choices.remove(option_value)
    else:
      selected_html = ''
    return format_html('<option value="{0}"{1}{2}>{3}</option>',
                         option_value, selected_html, label_html, force_text(option_label))
  
