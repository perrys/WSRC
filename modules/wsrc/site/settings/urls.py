from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

from django.contrib.auth import views as auth_views

import wsrc.site.competitions.data_urls
import wsrc.site.competitions.view_urls
import wsrc.site.competitions.legacy_urls

import wsrc.site.views
import wsrc.site.competitions.views
import wsrc.site.usermodel.views

urlpatterns = patterns('',

    url(r'^$', wsrc.site.views.index_view, name="homepage"),
    url(r'^home/?$', wsrc.site.views.index_view),
    url(r'^index/?$', wsrc.site.views.index_view),
    url(r'^memberlist/?$', wsrc.site.usermodel.views.MemberListView.as_view()),

    url(r'^login/?$', auth_views.login, {'template_name': 'login.html'}),
    url(r'^logout/?$', auth_views.logout),
    url(r'^password/reset/$',auth_views.password_reset,name='password_reset'),
    url(r'^password/reset/done/$',auth_views.password_reset_done,name='password_reset_done'),
    url(r'^password/reset/confirm/(?P<uidb64>[-\w]+)/(?P<token>[-\w]+)/$', auth_views.password_reset_confirm, name='password_reset_confirm'),
    url(r'^password/reset/complete/$',auth_views.password_reset_complete, name='password_reset_complete'),
    url(r'^password/change/$', auth_views.password_change, name='password_change'),
    url(r'^password/change/done/$', auth_views.password_change_done, name='password_change_done'),

    url(r'^boxes/(\d{4}-\d{2}-\d{2})/?$', wsrc.site.competitions.views.boxes_view), # end-date based
    url(r'^boxes/?$',                    wsrc.site.competitions.views.boxes_view), # most recent

    url(r'^tournament/(\d{4})/(\w+)/?$', wsrc.site.competitions.views.bracket_view),
    url(r'^tournament/?', wsrc.site.competitions.views.bracket_view, {"year":None, "name":"Open"}),

    url(r'^settings/?$', wsrc.site.views.settings_view),
    url(r'^change_password/?$', wsrc.site.views.change_password_view),

    url(r'^data/facebook$', wsrc.site.views.facebook_view),
    url(r'^data/',    include(wsrc.site.competitions.data_urls)),

    url(r'^tournaments/',  include(wsrc.site.competitions.legacy_urls)),

    url(r'^admin/', include(admin.site.urls)),

    url(r'^(?P<page>[a-z_]+)$', wsrc.site.views.generic_view),
)
