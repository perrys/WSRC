from django.conf.urls import include, url

from django.contrib import admin
admin.autodiscover()

from django.contrib.auth import views as auth_views
from django.shortcuts import redirect

import wsrc.site.competitions.data_urls
import wsrc.site.accounts.data_urls
from wsrc.site.usermodel.forms import SpaceTranslatingAuthenticationForm

import wsrc.site.views
import wsrc.site.accounts.views
import wsrc.site.competitions.views
import wsrc.site.courts.views
import wsrc.site.usermodel.views

def perm_redirect(view, permanent=True):
  def func(request):
    return redirect(view, permanent=permanent)
  return func 

urlpatterns = [


    url(r'^$',       wsrc.site.views.index_view, name="homepage"),
    url(r'^home/?$', wsrc.site.views.index_view),

    url(r'^login/?$',  wsrc.site.views.login, {'template_name': 'login.html', 'authentication_form': SpaceTranslatingAuthenticationForm}, name='login'),
    url(r'^logout/?$', auth_views.logout, name='logout'),

    url(r'^password/reset/$',auth_views.password_reset,name='password_reset'),
    url(r'^password/reset/done/$',auth_views.password_reset_done,name='password_reset_done'),
    url(r'^password/reset/confirm/(?P<uidb64>[-\w]+)/(?P<token>[-\w]+)/$', auth_views.password_reset_confirm, name='password_reset_confirm'),
    url(r'^password/reset/complete/$',auth_views.password_reset_complete, name='password_reset_complete'),
    url(r'^password/change/$', auth_views.password_change, name='password_change'),
    url(r'^password/change/done/$', auth_views.password_change_done, name='password_change_done'),

    url(r'^memberlist/?$', wsrc.site.usermodel.views.MemberListView.as_view(), name="member_list"),
    url(r'^maintenance/?$', wsrc.site.views.maintenance_view, name="maintenance"),
    url(r'^maintenance_issue/?$', wsrc.site.views.MaintenanceIssueCreateView.as_view(), name="create_maintenance_issue"),
    url(r'^suggestions/?$', wsrc.site.views.suggestions_view, name="suggestions"),
    url(r'^suggestion/?$', wsrc.site.views.SuggestionCreateView.as_view(), name="create_suggestion"),

    url(r'^courts/?$', wsrc.site.courts.views.day_view_redirect),
    url(r'^courts/(\d{4}-\d{2}-\d{2})/?$', wsrc.site.courts.views.day_view_redirect),
    url(r'^courts/day/?$', wsrc.site.courts.views.day_view, name="courts"),
    url(r'^courts/day/(\d{4}-\d{2}-\d{2})/?$', wsrc.site.courts.views.day_view),
    url(r'^courts/day/admin/(\d{4}-\d{2}-\d{2})/?$', wsrc.site.courts.views.day_view_admin, name="courts_admin"),
    url(r'^courts/booking/?$', wsrc.site.courts.views.edit_entry_view, name="booking"),
    url(r'^courts/booking/admin/?$', wsrc.site.courts.views.edit_entry_admin_view, name="booking_admin"),
    url(r'^courts/booking/(\d+)/?$', wsrc.site.courts.views.edit_entry_view),
    url(r'^courts/booking/admin/(\d+)/?$', wsrc.site.courts.views.edit_entry_admin_view),
    url(r'^courts/cal_invite/?$', wsrc.site.courts.views.calendar_invite_view, name="cal_invite"),
    url(r'^courts/cal_invite/(\d+)/?$', wsrc.site.courts.views.calendar_invite_view),
    url(r'^courts/agenda/?$', wsrc.site.courts.views.agenda_view, name="agenda"),
    url(r'^courts/notifications/?$', wsrc.site.courts.views.notifier_view, name="notifier"),
    url(r'^courts/penalty_points/?$', wsrc.site.courts.views.penalty_points_view, name="penalty_points"),
    url(r'^courts/condensation_report/?$', wsrc.site.courts.views.CondensationReportCreateView.as_view(), name="condensation_report"),
                       
    url(r'^competitions/admin/activate/',              wsrc.site.competitions.views.SetCompetitionGroupLive.as_view(), name="comp_group_activate"),
    url(r'^competitions/admin/email/',                 wsrc.site.competitions.views.SendCompetitionEmail.as_view()),

    url(r'^competitions/leagues/(?P<comp_type>\w+)/admin/?$',  wsrc.site.competitions.views.BoxesAdminView.as_view(), name=wsrc.site.competitions.views.BoxesAdminView.reverse_url_name),
    url(r'^competitions/leagues/(?P<comp_type>\w+)/admin/(?P<end_date>\d{4}-\d{2}-\d{2})/?$', wsrc.site.competitions.views.BoxesAdminView.as_view()),
    url(r'^competitions/leagues/(?P<comp_type>\w+)/xl/?$',                        wsrc.site.competitions.views.BoxesExcelView.as_view()),
    url(r'^competitions/leagues/(?P<comp_type>\w+)/xl/(?P<end_date>\d{4}-\d{2}-\d{2})/?$',    wsrc.site.competitions.views.BoxesExcelView.as_view()),

    url(r'^competitions/leagues/(?P<comp_type>\w+)/preview/(?P<group_id>\d+)/?$', wsrc.site.competitions.views.BoxesPreviewView.as_view(), name='leagues_preview'),
                       
    url(r'^competitions/leagues/(?P<comp_type>\w+)/(?P<end_date>\d{4}-\d{2}-\d{2})/?$', wsrc.site.competitions.views.BoxesUserView.as_view()), # end-date based
    url(r'^competitions/leagues/(?P<comp_type>\w+)/?$',                     wsrc.site.competitions.views.BoxesUserView.as_view(), \
        name=wsrc.site.competitions.views.BoxesUserView.reverse_url_name),
  
    url(r'^tournaments/admin/(\d{4})/([\w\s]+)/?',  wsrc.site.competitions.views.bracket_admin_view),
    url(r'^tournaments/admin/?',                    wsrc.site.competitions.views.bracket_admin_view),
#    url(r'^tournaments/qualifiers/(?P<year>\d{4})/(?P<name>[\w\s]+)?', wsrc.site.competitions.views.boxes_view, {'comp_type': 'qualifiers'}),
    url(r'^tournaments/(\d{4})/([\w\s]+)/print/?$', wsrc.site.competitions.views.bracket_view, {'template_name': 'tournaments_printable.html'}),
    url(r'^tournaments/(\d{4})/([\w\s]+)/?$',       wsrc.site.competitions.views.bracket_view, name="tournament"),
    url(r'^tournaments/?',                          wsrc.site.competitions.views.bracket_view, {"year":None, "name":"Squash Open"} , name="tournaments"),

    url(r'^competition/(?P<comp_id>\d+)/match/update/?$', wsrc.site.competitions.views.MatchChooseAndUpdateView.as_view(competition=None), name='match_choose_and_update'),
    url(r'^competition/(?P<comp_id>\d+)/match/(?P<pk>\d+)/?$', wsrc.site.competitions.views.MatchUpdateView.as_view(competition=None), name='match_update'),
    url(r'^competition/(?P<comp_id>\d+)/match/?$', wsrc.site.competitions.views.MatchCreateView.as_view(competition=None), name="match_create"),

    url(r'^training/ghosting/?$', wsrc.site.views.generic_get_template_view, {'template_name': 'ghost_training.html'}, name="ghosting"),

    url(r'^settings/?$', wsrc.site.usermodel.views.settings_view, name="settings"),

    url(r'^membership_application/?$', wsrc.site.usermodel.views.MembershipApplicationCreateView.as_view(),\
        name="membership_application"),
    url(r'^membership_application/submitted/?$', wsrc.site.views.generic_view, kwargs={"page": "MembershipApp_Submitted"},\
        name="membership_application_submitted"),
    url(r'^membership_application/(?P<pk>\d+)/verify_email/?$', wsrc.site.usermodel.views.MembershipApplicationVerifiedEmailView.as_view(),\
        name="membership_application_verify_email"),                       
    url(r'^membership_application/verify_email_failed/?$', wsrc.site.views.generic_view, kwargs={"page": "MembershipApp_VerifyFailed"},\
        name="membership_application_verify_email_failed"),

    url(r'^kiosk/?$', wsrc.site.views.kiosk_view, name="kiosk"),
                       

    url(r'^data/oauth_token_exchange/(.+)$', wsrc.site.views.OAuthExchangeTokenView.as_view(), name="oauth_token_exchange"),
    url(r'^data/facebook$', wsrc.site.views.facebook_view, name="facebook"),
    url(r'^data/bookings$', wsrc.site.views.BookingList.as_view()),
    url(r'^data/accounts/',  include(wsrc.site.accounts.data_urls)),
    url(r'^data/auth/', wsrc.site.views.auth_view),
    url(r'^data/club_events/', wsrc.site.views.ClubEventList.as_view()),
    url(r'^data/activity_report', wsrc.site.usermodel.views.member_activity_view),                       
    url(r'^data/',    include(wsrc.site.competitions.data_urls)),
    url(r'^data/doorcardevent/$', wsrc.site.usermodel.views.DoorCardEventCreateView.as_view()),

    url(r'^accounts/download/(\w+)', wsrc.site.accounts.views.transaction_csv_view),
    url(r'^accounts/?$', wsrc.site.accounts.views.accounts_view),
                       

    url(r'^admin/mailshot/send', wsrc.site.views.SendEmail.as_view()),
    url(r'^admin/mailshot/?', wsrc.site.views.admin_mailshot_view),
    url(r'^admin/', admin.site.urls),

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
    url(r'^boxes/?$',                 perm_redirect('/competitions/leagues/squash_boxes/')),
    url(r'^boxes/admin/?$',           perm_redirect('/competitions/leagues/squash_boxes/admin')),

    url(r'^club_management/?$', wsrc.site.views.committee_view),
    url(r'^committee/?$', wsrc.site.views.committee_view),
    url(r'^about/?$', wsrc.site.views.generic_nav_view, kwargs={"page": "about", "template": "about.html"}),
    url(r'^robots.txt$', wsrc.site.views.generic_txt_view, kwargs={"page": "robots.txt"}),
    url(r'^(?P<page>[a-z_]+)$', wsrc.site.views.generic_view),
]

from django.conf import settings
from django.conf.urls import include, url
