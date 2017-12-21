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

from django.core.urlresolvers import reverse

from wsrc.site.models import NavigationLink, NavigationNode
from collections import namedtuple

node_t = namedtuple("Node", ["pk", "is_restricted", "name", "children", "is_expanded"])

class NavigationMiddleWare:
    def process_template_response(self, request, response):
        nodes = NavigationNode.objects.filter(ordering__gt=0)
        links = NavigationLink.objects.filter(ordering__gt=0)
        if not request.user.is_authenticated():
            nodes = nodes.exclude(is_restricted=True)
            links = links.exclude(is_restricted=True)
        nodes = [node_t(node.pk, node.is_restricted, node.name, [], False) for node in nodes]
        nodes_map = dict([(n.pk, n) for n in nodes])
        for link in links:
            if link.parent_id is not None:
                parent = nodes_map[link.parent_id]
                parent.children.append(link)
                del nodes_map[link.pk]
                url = reverse(link.url) if link.is_reverse_url else link.url
                if request.path.startswith(url):
                    nodes_map[link.parent_id] = parent._replace(is_expanded=True)
            else:
                nodes_map[link.pk] = link
        nodes = [nodes_map[node.pk] for node in nodes if node.pk in nodes_map]
        response.context_data["navlinks"] = nodes
        return response
