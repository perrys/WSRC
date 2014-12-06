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

from django.conf.urls import patterns, url

import wsrc.site.competitions.views as views

urlpatterns = patterns('',
    url(r'^leagues/$', views.boxes_view, {"group_id": "0"}),
    url(r'^leagues/(-?[0-9]+)$', views.boxes_view),
    url(r'^tournament/(-?[0-9]+)$', views.bracket_view),
)

