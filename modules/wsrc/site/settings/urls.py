from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

import django.contrib.auth.views

import wsrc.site.competitions.data_urls
import wsrc.site.competitions.view_urls
import wsrc.site.competitions.legacy_urls

import wsrc.site.views
import wsrc.site.competitions.views

urlpatterns = patterns('',

    url(r'^$', wsrc.site.views.index_view, name="homepage"),
    url(r'^home$', wsrc.site.views.index_view),
    url(r'^index$', wsrc.site.views.index_view),
    url(r'^data/facebook$', wsrc.site.views.facebook_view),

    url(r'^login$', django.contrib.auth.views.login, {'template_name': 'login.html'}),
    url(r'^logout$', django.contrib.auth.views.logout),

    url(r'^tournament/(\d{4})/(\w+)$', wsrc.site.competitions.views.bracket_view),

    url(r'^comp_data/',    include(wsrc.site.competitions.data_urls)),
    url(r'^competitions/', include(wsrc.site.competitions.view_urls)),
    url(r'^tournaments/',  include(wsrc.site.competitions.legacy_urls)),

    url(r'^admin/', include(admin.site.urls)),

    url(r'^(?P<page>[a-z_]+)$', wsrc.site.views.generic_view),
)
