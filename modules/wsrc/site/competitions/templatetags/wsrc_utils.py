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

from django.template import Library, Node, Variable, VariableDoesNotExist
import wsrc.utils.text as text_utils

register = Library()

@register.filter
def keyvalue(dict, key):    
    return dict[key]

@register.filter
def parse_float(str):    
    return float(str)

@register.filter
def mins_to_duration_str(n):    
    hours = n / 60
    mins  = n % 60
    result = ""
    if hours > 0:
      result += "{hours} hour{p} ".format(hours=hours, p=text_utils.plural(hours))
    if mins > 0:
      result += "{mins} min{p} ".format(mins=mins, p=text_utils.plural(mins))
    return result

@register.filter
def mins_to_time_str(n):    
    return "{0:02d}:{1:02d}".format(n/60, n%60)

@register.tag
def make_text_table(parser, token):
    tag_name = "make_text_table"
    try:
        tokens = token.split_contents()
        tag_name = tokens.pop(0)
        variable_name = tokens.pop(0)
        if len(tokens) < 2 or (len(tokens) & 1) == 1:
            raise ValueError()
        fields = []
        for i in range(0, len(tokens), 2):
            fields.append((tokens[i], tokens[i+1]))
    except ValueError:
        raise template.TemplateSyntaxError("%(tag_name)s tag requires at least two arguments" % locals())
    return TextTableNode(variable_name, *fields)

class TextTableNode(Node):
    def __init__(self, variable_name, *fields):
        self.variable = Variable(variable_name)
        self.fields = fields
        
    def render(self, context):
        raw_rows = self.variable.resolve(context)
        ordered_rows = []
        def st(s):
            if s == "__": return ""
            return s
        headers = [st(field[0]) for field in self.fields]
        has_headers = False
        for h in headers:
            if len(h) > 0:
                has_headers = True
                break
        if has_headers:
            ordered_rows.append(headers)
        for row in raw_rows:
            ordered_rows.append([self.get_val(row, field[1]) for field in self.fields])
        return text_utils.formatTable(ordered_rows, has_headers)
    def get_val(self, record, field):
        if field.startswith("__"):
          return field[2:]
        for tok in field.split("."):
            if hasattr(record, tok):
                record = getattr(record, tok)
            else:
                record = record[tok]
            if hasattr(record, "__call__"):
                record = record()
        return record
