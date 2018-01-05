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

def formatTable(dataTable, hasHeader = False, nspaces=1):
    maxlengths = []
    buf = ""
    data = []
    for row in dataTable:
        data.append([cell or "" for cell in row])

    spaces = " " * nspaces

    for row in data:
        for i,cell in enumerate(row):
            while len(maxlengths) <= i:
                maxlengths.append(0)
            maxlengths[i] = max(maxlengths[i], len(cell))
    for i,row in enumerate(data):
        if hasHeader and i == 1:
            buf += spaces.join(["-" * l for l in maxlengths]) + "\n"
        buf += spaces.join([cell.ljust(maxlengths[i]) for i,cell in enumerate(row)]) + "\n"

    return buf

def plural(l, extra=""):
    if isinstance(l, int):
        n = l
    else:
        n = len(l)
    if n == 1:
        return ""
    return extra + "s"

def shorten(text, max_words):
    words = text.split(" ")
    if len(words) > max_words:
        return " ".join(words[:max_words]) + "..."
    return text

def obfuscate(astr):
    if len(astr) <= 1:
        return astr
    return astr[0] + "".join(['_'] * (len(astr)-1))
