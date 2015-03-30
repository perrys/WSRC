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

import wsrc.site.accounts.views as views

urlpatterns = patterns('',
    url(r'^account/$', views.AccountListView.as_view()),
    url(r'^account/(?P<pk>[0-9]*)$', views.AccountView.as_view()),
    url(r'^account/transactions/(?P<account_name>\w*)$', views.TransactionView.as_view()),
    url(r'^account/category/$', views.CategoryListView.as_view()),
    url(r'^account/category/(?P<pk>[0-9]*)$', views.CategoryDetailView.as_view()),
)

urlpatterns = format_suffix_patterns(urlpatterns)
