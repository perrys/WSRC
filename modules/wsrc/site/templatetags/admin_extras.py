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

import csv
import StringIO

import django.contrib.admin.templatetags.admin_list as base_templatetags
from django.template import Library
from django.contrib.admin.utils import (
    display_for_field, display_for_value, get_fields_from_path,
    label_for_field, lookup_field,
)
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe

register = Library()

@register.simple_tag
def result_list_csv(cl):
    """
    Displays the headers and data list as CSV rows
    """
    headers = list(base_templatetags.result_headers(cl))
    buf = StringIO.StringIO()
    writer = csv.writer(buf)
    writer.writerow([header["text"].encode("utf-8") for header in headers[1:]])
    empty_value_display = ""
    for result in cl.result_list:
        row = []
        for field_index, field_name in enumerate(cl.list_display):
            if field_index == 0:
                continue # skip the checkbox
            try:
                field, attr, value = lookup_field(field_name, result, cl.model_admin)
                result_repr = force_text(value)
            except ObjectDoesNotExist:
                result_repr = empty_value_display
            row.append(result_repr.encode("utf-8"))
        writer.writerow(row)
    buf.flush()
    return mark_safe(buf.getvalue())
