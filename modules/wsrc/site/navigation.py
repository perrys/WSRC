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

"Middleware to insert navigation data into template context"

from wsrc.site.models import NavigationLink

class NavigationMiddleWare:
    def process_template_response(self, request, response):
        links = NavigationLink.objects.filter(ordering__gt=0)
        if not request.user.is_authenticated():
            links = links.exclude(is_restricted=True)
        response.context_data["navlinks"] = links
        return response
