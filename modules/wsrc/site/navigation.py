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
        navnode_model_records = NavigationNode.objects.tree(request.user.is_authenticated)
        # create a map of proxy nodes - we will arrange this into a
        # tree structure with only the root nodes remaining in the map
        proxy_nodes = [node_t(node.pk, node.name, [], False) for node in navnode_model_records]
        navnode_proxy_map = dict([(n.pk, n) for n in proxy_nodes])
        for link in [node for node in navnode_model_records if hasattr(node, "url")]:
            if link.is_reverse_url:
                args = link.url.split("::")
                url_name = args[0]
                args = args[1:]
                url = reverse(url_name, args=args)
            else:
                url = link.url
            is_active = request.path.startswith(url)
            link_proxy = link_t(link.pk, link.name, url, is_active)
            if link.parent_id is not None:
                parent = navnode_proxy_map[link.parent_id]
                if is_active:
                    navnode_proxy_map[link.parent_id] = parent._replace(is_expanded=True)
                parent.children.append(link_proxy)
                del navnode_proxy_map[link.pk] # remove this leaf from the map
            else:
                navnode_proxy_map[link.pk] = link_proxy

        # create a list of top-level nodes in the original model order:
        nodes = [navnode_proxy_map[node.pk] for node in navnode_model_records if node.pk in navnode_proxy_map]
        if response.context_data is None:
            response.context_data = {"navlinks": nodes}
        else:
            response.context_data["navlinks"] = nodes
        return response
