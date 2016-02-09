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


from django.forms.fields import CharField
from django.contrib.auth.forms import AuthenticationForm

class SpaceTranslatingCharField(CharField):
    def to_python(self, value):
        value = super(SpaceTranslatingCharField, self).to_python(value)
        print value
        value = value.replace(" ", "_")
        print value
        return value

class SpaceTranslatingAuthenticationForm(AuthenticationForm):
    # allow spaces in usernames, which will be translated to underscores
    username = SpaceTranslatingCharField(max_length=254)