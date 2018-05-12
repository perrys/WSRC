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

from markdown.extensions import Extension
from markdown.inlinepatterns import Pattern
from markdown.util import etree

REDACTED_OR_EMPTY_PATTERN = r"<([^> ]*--redacted--[^> ]*|\s*)>"
TELEPHONE_NUMBER_PATTERN = r"<(\+?[\d\s]+)>"


class RedactedPattern(Pattern):
    def handleMatch(self, m):
        link = self.unescape(m.group(2)).strip()
        return link
    
class TelephonePattern(Pattern):
    def handleMatch(self, m):
        link = self.unescape(m.group(2))
        number = link.replace(" ", "")
        el = etree.Element('a')
        el.text = link
        if link.startswith("+447") or link.startswith("07"):
            el.set('href', "sms:" + number)
        else:
            el.set('href', "tel:" + number)
        return el

class RedactedLinkExtension(Extension):
    def extendMarkdown(self, md, md_globals):
        md.inlinePatterns.add('autoredact', RedactedPattern(REDACTED_OR_EMPTY_PATTERN, md), '_begin')
        md.inlinePatterns.add('autotel',    TelephonePattern(TELEPHONE_NUMBER_PATTERN, md), '>automail')
