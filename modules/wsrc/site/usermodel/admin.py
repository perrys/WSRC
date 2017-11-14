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

"Admin for the membership models"

from django import forms
from django.db import models

from django.contrib import admin

from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.models import User

from django.core import urlresolvers

from .models import Player, Season, Subscription, SubscriptionPayment, SubscriptionCost
from wsrc.utils.form_utils import SelectRelatedQuerysetMixin, CachingModelChoiceField, \
    get_related_field_limited_queryset, PrefetchRelatedQuerysetMixin

class UserProfileInline(admin.StackedInline):
    "Simple inline for player in User admin"
    model = Player
    max_num = 1
    can_delete = False

class UserAdmin(AuthUserAdmin):
    "Redefinition of user admin"
    inlines = AuthUserAdmin.inlines + [UserProfileInline,]
    list_display = ('username', 'is_active', 'membership_type', 'email', \
                    'first_name', 'last_name', 'cardnumber', 'booking_system_id', 'is_staff')
    list_filter = ('is_active', 'player__membership_type', 'groups', \
                   'player__prefs_esra_member', 'is_staff', 'is_superuser')
    ordering = ('username', 'first_name', 'last_name')
    list_per_page = 400

    def get_queryset(self, request):
        queryset = super(UserAdmin, self).get_queryset(request)
        queryset = queryset.select_related('player')
        return queryset

    def booking_system_id(self, obj):
        return obj.player.booking_system_id
    booking_system_id.short_description = "Booking Site ID"
    booking_system_id.admin_order_field = "player__booking_system_id"

    def membership_type(self, obj):
        return obj.player.membership_type
    membership_type.short_description = "Type"
    membership_type.admin_order_field = 'player__membership_type'

    def cardnumber(self, obj):
        return obj.player.cardnumber
    cardnumber.short_description = "DoorCard #"
    cardnumber.admin_order_field = 'player__cardnumber'

# unregister old user admin
admin.site.unregister(User)
# register new user admin
admin.site.register(User, UserAdmin)

class SeasonAdmin(admin.ModelAdmin):
    "Simple admin for Seasons"
    list_display = ('__unicode__', "has_ended")
    list_editable = ("has_ended",)

class SubscriptionForm(forms.ModelForm):
    "Override subscription form for more efficient DB interaction"
    queryset = get_related_field_limited_queryset(Subscription.player.field)
    player = forms.ModelChoiceField(queryset=queryset.select_related("user"))

class SubscriptionPaymentForm(forms.ModelForm):
    "Override subscription payment form for more efficient DB interaction"
    queryset = get_related_field_limited_queryset(SubscriptionPayment.transaction.field)
    transaction = CachingModelChoiceField(queryset=queryset)

class SubscriptionPaymentInline(SelectRelatedQuerysetMixin, admin.StackedInline):
    "Simple inline for subs payments"
    model = SubscriptionPayment
    can_delete = True
    form = SubscriptionPaymentForm

class SeasonListFilter(admin.SimpleListFilter):
    "Simple filtering on Season"
    title = "Season"
    parameter_name = "season"
    def lookups(self, request, model_admin):
        return [(s.id, unicode(s)) for s in Season.objects.all()]
    def queryset(self, request, queryset):
        if self.value():
            queryset = queryset.filter(season_id=self.value())
        return queryset

class SubscriptionAdmin(admin.ModelAdmin):
    "Subscription admin - heavilly used for subs management"
    inlines = (SubscriptionPaymentInline,)
    list_display = ('ordered_name', 'season', 'linked_membership_type', 'pro_rata_date',\
                    'payment_frequency', 'pro_rata_cost', 'payments_count', 'total_payments',\
                    'due_amount', 'signed_off', "comment")
    list_filter = (SeasonListFilter, 'signed_off', 'payment_frequency', 'player__membership_type', )
    list_editable = ('signed_off', 'comment')
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 30, 'rows': 1})},
    }
    form = SubscriptionForm
    list_per_page = 400

    def ordered_name(self, obj):
        return obj.player.get_ordered_name()
    ordered_name.admin_order_field = "player__user__last_name"
    ordered_name.short_description = "Name"

    def linked_membership_type(self, obj):
        link = urlresolvers.reverse("admin:usermodel_player_change", args=[obj.player.id])
        return u'<a href="%s">%s</a>' % (link, obj.player.get_membership_type_display())
    linked_membership_type.allow_tags = True
    linked_membership_type.short_description = "Membership Type"
    linked_membership_type.admin_order_field = "membership_type"

    def total_payments(self, obj):
        return "<span style='width:100%; display:inline-block; text-align:right;'>{0:.2f}</span>"\
            .format(obj.get_total_payments())
    total_payments.allow_tags = True
    total_payments.short_description = u"Paid (\xa3)"

    def pro_rata_cost(self, obj):
        return "<span style='width:100%; display:inline-block; text-align:right;'>{0:.2f}</span>"\
            .format(obj.get_pro_rata_cost())
    pro_rata_cost.allow_tags = True
    pro_rata_cost.short_description = u"Cost (\xa3)"

    def due_amount(self, obj):
        amount = obj.get_due_amount()
        style = ''
        if not obj.signed_off:
            if amount > 0:
                style = 'color: red'
            elif amount == 0:
                style = 'color: green'
        return "<span style='width:100%; display:inline-block; text-align:right; {1}'>{0:.2f}</span>"\
            .format(max(0, amount), style)
    due_amount.allow_tags = True
    due_amount.short_description = u"Due (\xa3)"

    def membership_type(self, obj):
        return obj.player.get_membership_type_display()
    membership_type.short_description = "Membership Type"
    membership_type.admin_order_field = "player__membership_type"

    def get_queryset(self, request):
        queryset = super(SubscriptionAdmin, self).get_queryset(request)
        queryset = queryset.select_related('player__user', 'season')
        queryset = queryset.prefetch_related('payments__transaction', 'season__costs')
        return queryset

def update_subscriptions(modeladmin, request, queryset):
    latest_season = Season.latest()
    queryset.prefetch_related("subscription_set__season")
    for player in queryset:
        found = False
        subscription = None
        for subscription in player.subscription_set.all():
            if subscription.season_id == latest_season.id:
                found = True
                break
        if not found:
            payment_freq = "annual" if subscription is None else subscription.payment_frequency
            sub = Subscription(player=player, season=latest_season, payment_frequency=payment_freq)
            sub.save()
update_subscriptions.short_description = "Check/update subscriptions"

class PlayerAdmin(SelectRelatedQuerysetMixin, PrefetchRelatedQuerysetMixin, admin.ModelAdmin):
    "Admin for Player (i.e. club member) model"
    list_filter = ('user__is_active', 'membership_type', )
    list_display = ('ordered_name', 'active', 'date_joined_date', \
                    'membership_type', 'current_season', 'signed_off',
                    'cell_phone', 'other_phone',
                    'cardnumber', 'england_squash_id',
                    'prefs_receive_email', 'prefs_esra_member', 'prefs_display_contact_details')
    search_fields = ('user__first_name', 'user__last_name', 'cardnumber')
    prefetch_related_fields = ('subscription_set__season',)
    list_per_page = 400
    actions = (update_subscriptions,)

    def ordered_name(self, obj):
        return obj.get_ordered_name()
    ordered_name.admin_order_field = 'user__last_name'
    ordered_name.short_description = "Name"

    def active(self, obj):
        return obj.user.is_active
    active.admin_order_field = 'user__is_active'
    active.boolean = True

    def current_subscription(self, obj):
        subscriptions = obj.subscription_set.all()
        if subscriptions.count() > 0:
            return subscriptions[0]
        return None

    def current_season(self, obj):
        sub = self.current_subscription(obj)
        if sub is not None:
            return sub.season
        return None
    current_subscription.short_description = 'Subscription'

    def signed_off(self, obj):
        sub = self.current_subscription(obj)
        if sub is not None:
            return sub.signed_off
        return None
    signed_off.short_description = 'Signed Off'
    signed_off.boolean = True

    def date_joined_date(self, obj):
        return obj.user.date_joined.date()
    date_joined_date.short_description = "Joined"
    date_joined_date.admin_order_field = 'date_joined'

class SubscriptionCostAdmin(SelectRelatedQuerysetMixin, admin.ModelAdmin):
    list_display = ('membership_type', 'season', 'amount')

admin.site.register(Season, SeasonAdmin)
admin.site.register(Subscription, SubscriptionAdmin)
admin.site.register(Player, PlayerAdmin)
admin.site.register(SubscriptionCost, SubscriptionCostAdmin)
