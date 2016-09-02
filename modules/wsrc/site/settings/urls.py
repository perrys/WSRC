from django.conf.urls import patterns, include, url

from django.contrib import admin
admin.autodiscover()

from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

import wsrc.site.competitions.data_urls
import wsrc.site.accounts.data_urls
import wsrc.site.usermodel.data_urls
from wsrc.site.usermodel.forms import SpaceTranslatingAuthenticationForm

import wsrc.site.views
import wsrc.site.accounts.views
import wsrc.site.competitions.views
import wsrc.site.usermodel.views

def perm_redirect(view, permanent=True):
  def func(request):
    return redirect(view, permanent=permanent)
  return func 

urlpatterns = patterns('',


    url(r'^$',       wsrc.site.views.index_view),
    url(r'^home/?$', wsrc.site.views.index_view, name="homepage"),

    url(r'^login/?$',  auth_views.login, {'template_name': 'login.html', 'authentication_form': SpaceTranslatingAuthenticationForm}),
    url(r'^logout/?$', auth_views.logout, name='logout'),
    url(r'^logout_dialog/?$', wsrc.site.views.logout_dialog_view, name='logout_dialog'),

    url(r'^password/reset/$',auth_views.password_reset,name='password_reset'),
    url(r'^password/reset/done/$',auth_views.password_reset_done,name='password_reset_done'),
    url(r'^password/reset/confirm/(?P<uidb64>[-\w]+)/(?P<token>[-\w]+)/$', auth_views.password_reset_confirm, name='password_reset_confirm'),
    url(r'^password/reset/complete/$',auth_views.password_reset_complete, name='password_reset_complete'),
    url(r'^password/change/$', auth_views.password_change, name='password_change'),
    url(r'^password/change/done/$', auth_views.password_change_done, name='password_change_done'),
    url(r'^change_password/?$', wsrc.site.views.change_password_view),

    url(r'^admin/memberlist/?', wsrc.site.usermodel.views.admin_memberlist_view),
    url(r'^memberlist/?$', wsrc.site.usermodel.views.MemberListView.as_view(), name="member_list"),
    url(r'^maintenance/?$', wsrc.site.views.maintenance_view, name="maintenance"),
    url(r'^suggestions/?$', wsrc.site.views.suggestions_view, name="suggestions"),
    url(r'^court_booking/?$', wsrc.site.views.booking_view, name="court_booking"),
    url(r'^court_booking/(\d{4}-\d{2}-\d{2})/?$', wsrc.site.views.booking_view, name="court_booking"),
    url(r'^court_booking/proxy/?$', wsrc.site.views.booking_proxy_view),

    url(r'^boxes/admin/activate/',              wsrc.site.competitions.views.SetCompetitionGroupLive.as_view()),
    url(r'^boxes/admin/email/',                 wsrc.site.competitions.views.SendCompetitionEmail.as_view()),
    url(r'^boxes/admin/?$',                     wsrc.site.competitions.views.boxes_view, {'template_name': 'boxes_admin.html', 'check_permissions': True}),
    url(r'^boxes/admin/(\d{4}-\d{2}-\d{2})/?$', wsrc.site.competitions.views.boxes_view, {'template_name': 'boxes_admin.html', 'check_permissions': True}),

    url(r'^boxes/(\d{4}-\d{2}-\d{2})/?$', wsrc.site.competitions.views.boxes_view), # end-date based
    url(r'^boxes/?$',                     wsrc.site.competitions.views.boxes_view, name="boxes"), # most recent

    url(r'^tournaments/admin/(\d{4})/([\w\s]+)/?',  wsrc.site.competitions.views.bracket_admin_view),
    url(r'^tournaments/admin/?',                    wsrc.site.competitions.views.bracket_admin_view),
    url(r'^tournaments/qualifiers/(?P<year>\d{4})/(?P<name>[\w\s]+)?', wsrc.site.competitions.views.boxes_view, {'comp_type': 'qualifiers'}),
    url(r'^tournaments/(\d{4})/([\w\s]+)/print/?$', wsrc.site.competitions.views.bracket_view, {'template_name': 'tournaments_printable.html'}),
    url(r'^tournaments/(\d{4})/([\w\s]+)/?$',       wsrc.site.competitions.views.bracket_view),
    url(r'^tournaments/?',                          wsrc.site.competitions.views.bracket_view, {"year":None, "name":"Open"} , name="tournaments"),

    url(r'^settings/?$', wsrc.site.views.settings_view, name="settings"),

    url(r'^data/facebook$', wsrc.site.views.facebook_view),
    url(r'^data/bookings$', wsrc.site.views.BookingList.as_view()),
    url(r'^data/accounts/',  include(wsrc.site.accounts.data_urls)),
    url(r'^data/memberlist/',  include(wsrc.site.usermodel.data_urls)),
    url(r'^data/auth/', wsrc.site.views.auth_view),
    url(r'^data/club_events/', wsrc.site.views.ClubEventList.as_view()),
    url(r'^data/',    include(wsrc.site.competitions.data_urls)),

    url(r'^accounts/download/(\w+)', wsrc.site.accounts.views.transaction_csv_view),
    url(r'^accounts/?$', wsrc.site.accounts.views.accounts_view),
                       

    url(r'^admin/mailshot/send', wsrc.site.views.SendEmail.as_view()),
    url(r'^admin/mailshot/?', wsrc.site.views.admin_mailshot_view),
    url(r'^admin/', include(admin.site.urls)),

    url(r'^html/club_history.html',   perm_redirect('/about')),
    url(r'^html/membership.html',     perm_redirect('/membership')),
    url(r'^html/how_to_find_us.html', perm_redirect('/contact')),
    url(r'^html/club_nights.html',    perm_redirect('/about')),
    url(r'^html/coaching.html',       perm_redirect('/coaching')),
    url(r'^html/juniors.html',        perm_redirect('/juniors')),
    url(r'^html/teams.html',          perm_redirect('/home')),
    url(r'^html/events.html',         perm_redirect('/home')),
    url(r'^html/news.php',            perm_redirect('/home')),
    url(r'^html/links.html',          perm_redirect('/links')),
    url(r'^tournaments/index.html',   perm_redirect('/tournament')),


    url(r'^(?P<page>[a-z_]+)$', wsrc.site.views.generic_view),
)
