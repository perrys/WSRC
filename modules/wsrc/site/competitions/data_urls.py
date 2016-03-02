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

import wsrc.site.competitions.views as views

urlpatterns = patterns('',
    url(r'^match/$', views.CreateMatch.as_view()),
    url(r'^match/(?P<pk>[0-9]*)$', views.UpdateMatch.as_view()),
    url(r'^players/$', views.PlayerList.as_view()),
    url(r'^player/(?P<pk>[0-9]+)$', views.PlayerDetail.as_view()),
    url(r'^competition/$', views.CompetitionList.as_view()),
    url(r'^competition/(?P<pk>[0-9]*)$', views.CompetitionDetail.as_view()),
    url(r'^competitiongroup/$', views.CompetitionGroupList.as_view()),
    url(r'^competitiongroup/(?P<pk>[0-9]+)$', views.CompetitionGroupDetail.as_view()),
    url(r'^competition/tournament/(?P<pk>[0-9]*)$', views.UpdateTournament.as_view()),
)

urlpatterns = format_suffix_patterns(urlpatterns)
