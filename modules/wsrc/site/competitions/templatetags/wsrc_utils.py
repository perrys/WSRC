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
        ordered_rows = [[field[0] for field in self.fields]]
        for row in raw_rows:
            ordered_rows.append([self.get_val(row, field[1]) for field in self.fields])
        return text_utils.formatTable(ordered_rows, True)
    def get_val(self, record, field):
        for tok in field.split("."):
            if hasattr(record, tok):
                record = getattr(record, tok)
            else:
                record = record[tok]
            if hasattr(record, "__call__"):
                record = record()
        return record
