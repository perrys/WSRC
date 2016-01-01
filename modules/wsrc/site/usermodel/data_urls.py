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
from rest_framework.urlpatterns import format_suffix_patterns

import wsrc.site.usermodel.views as views

urlpatterns = patterns('',
    url(r'^player/$', views.PlayerListView.as_view()),
    url(r'^player/(?P<pk>[0-9]*)$', views.PlayerView.as_view()),
    url(r'^user/(?P<pk>[0-9]*)$', views.UserView.as_view()),
)

urlpatterns = format_suffix_patterns(urlpatterns)