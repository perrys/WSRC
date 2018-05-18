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

from django.urls import reverse

from wsrc.site.models import NavigationLink, NavigationNode
from collections import namedtuple

node_t = namedtuple("Node", ["pk", "name", "children", "is_expanded"])
link_t = namedtuple("Link", ["pk", "name", "url", "is_active"])

class NavigationMiddleWare:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_template_response(self, request, response):
        tree_nodes = NavigationNode.objects.tree(request.user.is_authenticated())
        nodes = [node_t(node.pk, node.name, [], False) for node in tree_nodes]
        nodes_map = dict([(n.pk, n) for n in nodes])
        for link in [node for node in tree_nodes if hasattr(node, "url")]:
            if link.parent_id is not None:
                parent = nodes_map[link.parent_id]
                url = reverse(link.url) if link.is_reverse_url else link.url
                if request.path.startswith(url):
                    nodes_map[link.parent_id] = parent._replace(is_expanded=True)
                    link = link_t(link.pk, link.name, url, True)
                parent.children.append(link)
                del nodes_map[link.pk]
            else:
                url = reverse(link.url) if link.is_reverse_url else link.url
                if request.path.startswith(url):
                    link = link_t(link.pk, link.name, link.url, True)
                nodes_map[link.pk] = link

        nodes = [nodes_map[node.pk] for node in tree_nodes if node.pk in nodes_map]
        if response.context_data is None:
            response.context_data = {"navlinks": nodes}
        else:
            response.context_data["navlinks"] = nodes
        return response
