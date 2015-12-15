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

from django import forms

def upload_generator(upload):
    last_line = ""
    for chunk in upload.chunks():
        lines = (last_line + chunk).split("\n")
        for i, line in enumerate(lines):
            if i < (len(lines) -1):
                yield line
            else:
                last_line = line
    if len(last_line) > 0:
        yield last_line

class UploadFileForm(forms.Form):
    file = forms.FileField()

