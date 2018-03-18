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

import csv
import datetime
import StringIO

from django import forms
from django.db import models

from django.contrib import admin

from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.models import User

from django.core import urlresolvers
from django.http import HttpResponse

from .models import Player, Season, Subscription, SubscriptionPayment,\
    SubscriptionCost, SubscriptionType, DoorEntryCard, DoorCardEvent, DoorCardLease
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
    list_display = ('username', 'last_name', 'first_name', 'email',\
                    'is_active', 'is_staff', 'last_login', 'date_joined')
    list_filter = ('is_active', 'groups', 'is_staff', 'is_superuser')
    ordering = ('last_name', 'first_name', 'username')
    list_per_page = 400
    list_select_related = ('player',)

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

def remove_and_inactivate(modeladmin, request, queryset):
    for subscription in queryset:
        if subscription.signed_off or subscription.payments_count() > 0:
            continue
        user = subscription.player.user
        user.is_active = False
        user.save()
        subscription.delete()
remove_and_inactivate.short_description = "Remove Subscripiton & Set Inactive"
    
class SubscriptionAdmin(admin.ModelAdmin):
    "Subscription admin - heavilly used for subs management"
    inlines = (SubscriptionPaymentInline,)
    list_display = ('ordered_name', 'email', 'season', 'linked_membership_type', 'pro_rata_date',\
                    'payment_frequency', 'pro_rata_cost', 'payments_count', 'total_payments',\
                    'due_amount', 'signed_off', "comment")
    list_filter = (SeasonListFilter, 'signed_off', 'payment_frequency', 'subscription_type', )
    list_editable = ('signed_off', 'comment')
    formfield_overrides = {
        models.TextField: {'widget': forms.TextInput(attrs={'size': 30})},
    }
    form = SubscriptionForm
    list_per_page = 400
    search_fields = ('player__user__first_name', 'player__user__last_name')
    actions = (remove_and_inactivate,)

    def email(self, obj):
        return obj.player.user.email
    email.admin_order_field = "player__user__email"
    email.short_description = "Email"

    def ordered_name(self, obj):
        return obj.player.get_ordered_name()
    ordered_name.admin_order_field = "player__user__last_name"
    ordered_name.short_description = "Name"

    def linked_membership_type(self, obj):
        link = urlresolvers.reverse("admin:usermodel_player_change", args=[obj.player.id])
        return u'<a href="%s">%s</a>' % (link, obj.subscription_type.name)
    linked_membership_type.allow_tags = True
    linked_membership_type.short_description = "Type"
    linked_membership_type.admin_order_field = "subscription_type"

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

    def get_queryset(self, request):
        queryset = super(SubscriptionAdmin, self).get_queryset(request)
        queryset = queryset.select_related('player__user', 'season', 'subscription_type')
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
        if not found and player.user.is_active:
            payment_freq = "annual" if subscription is None else subscription.payment_frequency
            if subscription is not None:
                subs_type = subscription.subscription_type
            else:
                subs_type = SubscriptionType.objects.get(is_default=True)
                if player.date_of_birth is not None:
                    age_restricted_types = SubscriptionType.\
                                           objects.filter(max_age_years__isnull=False)\
                                                  .order_by("max_age_years")
                    age_years = player.get_age()
                    for i_substype in age_restricted_types:
                        if age_years <= i_substype.max_age_years:
                            subs_type = i_substype
                            break
            subscription = Subscription(player=player, season=latest_season,
                                        payment_frequency=payment_freq, subscription_type=subs_type)
            subscription.save()
        elif found and not player.user.is_active:
            subscription.delete()
            
update_subscriptions.short_description = "Check/update subscriptions"

class HasESIDListFilter(admin.SimpleListFilter):
    "Simple filtering on ES ID not null"
    title = "Has ES ID"
    parameter_name = "has_es_id"
    def lookups(self, request, model_admin):
        return [('y', 'Yes'), ('n', 'No')]
    def queryset(self, request, queryset):
        if self.value():
            yes_flag = self.value() == 'y'
            if yes_flag:
                queryset = queryset.filter(models.Q(england_squash_id__isnull=False)\
                                           & ~models.Q(england_squash_id=''))
            else:
                queryset = queryset.filter(models.Q(england_squash_id__isnull=True)\
                                           | models.Q(england_squash_id=''))
        return queryset


class SubscriptionInline(admin.StackedInline):
    "Simple inline for player in User admin"
    model = Subscription
    max_num = 1
    formfield_overrides = {
        models.TextField: {'widget': forms.TextInput(attrs={'size': 40})},
    }

class PlayerListUploadForm(forms.Form):
    es_csv_file = forms.FileField(required=False, label="Click to select England Squash csv file. ",
                                  widget=forms.widgets.ClearableFileInput(attrs={'accept':'.csv'}))

class DoorCardLeaseForm(forms.ModelForm):
    "Override form for more efficient DB interaction"
    queryset = get_related_field_limited_queryset(DoorCardLease.player.field)
    player = forms.ModelChoiceField(queryset=queryset.select_related("user"), required=False)
    player.label = "Owner"


class DoorCardLeaseInline(admin.TabularInline):
    model = DoorCardLease
    form = DoorCardLeaseForm

class PlayerAdmin(SelectRelatedQuerysetMixin, PrefetchRelatedQuerysetMixin, admin.ModelAdmin):
    "Admin for Player (i.e. club member) model"
    list_filter = ('user__is_active', 'subscription__subscription_type', HasESIDListFilter)
    list_display = ('ordered_name', 'active', 'date_joined_date', \
                    'get_age', 'subscription_type', 'current_season', 'signed_off',
                    'cell_phone', 'other_phone', 'booking_system_id', 'england_squash_id',
                    'prefs_receive_email', 'prefs_esra_member', 'prefs_display_contact_details')
    search_fields = ('user__first_name', 'user__last_name')
    prefetch_related_fields = ('subscription_set__season','subscription_set__subscription_type')
    list_per_page = 400
    actions = (update_subscriptions,)
    inlines = (SubscriptionInline,DoorCardLeaseInline)
    readonly_fields = ("user_link", "date_joined_date", "doorcard_numbers")
    exclude = ("user",)

    def ordered_name(self, obj):
        return obj.get_ordered_name()
    ordered_name.admin_order_field = 'user__last_name'
    ordered_name.short_description = "Name"

    def active(self, obj):
        return obj.user.is_active
    active.admin_order_field = 'user__is_active'
    active.boolean = True

    def current_season(self, obj):
        sub = obj.get_current_subscription()
        if sub is not None:
            return sub.season
        return None
    current_season.short_description = "Season"
    current_season.admin_order_field = "subscription__season"

    def subscription_type(self, obj):
        sub = obj.get_current_subscription()
        if sub is not None:
            return sub.subscription_type.name
        return None
    subscription_type.short_description = "Subs Type"
    subscription_type.admin_order_field = "subscription__subscription_type__name"
    
    def signed_off(self, obj):
        sub = obj.get_current_subscription()
        if sub is not None:
            return sub.signed_off
        return None
    signed_off.short_description = 'Signed Off'
    signed_off.boolean = True

    def user_link(self, obj):
        link = urlresolvers.reverse("admin:auth_user_change", args=[obj.user.id])
        link = u'<a id="user_link" href="{0}" style="font-weight: bold" data-name="{1}" data-email="{2}">{3}</a>'\
               .format(link, obj.user.get_full_name(), obj.user.email, obj.get_ordered_name())
        return link
    user_link.short_description = "User"
    user_link.allow_tags = True

    def date_joined_date(self, obj):
        return obj.user.date_joined.date()
    date_joined_date.short_description = "Joined"
    date_joined_date.admin_order_field = 'user__date_joined'

    def doorcard_numbers(self, obj):
        numbers = [str(o.cardnumber) for o in obj.doorcards.all()]
        return '<span id="door_cards">{0}</span>'.format(", ".join(numbers))
    doorcard_numbers.short_description = "Door Cards"
    doorcard_numbers.allow_tags = True

    def get_urls(self):
        from django.conf.urls import patterns, url
        urls = super(PlayerAdmin, self).get_urls()
        my_urls = patterns("", url(r"^upload_es_csv/$", self.admin_site.admin_view(self.upload_csv_view),
                                   name='upload_es_csv'))
        return my_urls + urls
    urls = property(get_urls)

    def changelist_view(self, *args, **kwargs):
        view = super(PlayerAdmin, self).changelist_view(*args, **kwargs)
        view.context_data['upload_csv_form'] = PlayerListUploadForm
        return view

    def upload_csv_view(self, request):
        if request.method == 'POST':
            form = PlayerListUploadForm(request.POST, request.FILES)
            if form.is_valid():
                members = Player.objects.all().select_related("user")\
                                              .prefetch_related("subscription_set__subscription_type")\
                                              .prefetch_related("subscription_set__season")
                es_id_map = dict([(mem.england_squash_id, mem) for mem in members\
                                  if mem.england_squash_id is not None\
                                  and len(mem.england_squash_id) > 0])
                db_id_map = dict([(mem.pk, mem) for mem in members])
                name_map = dict([(mem.get_ordered_name(), mem) for mem in members])
                from wsrc.utils.upload_utils import upload_generator
                reader = csv.DictReader(upload_generator(request.FILES['es_csv_file']))
                output = StringIO.StringIO()
                fields = ["ES ID", "Name", "WSRC Name", "WSRC ID", "Email", "Subscription", "Status"]
                writer = csv.DictWriter(output, fields, extrasaction='ignore')
                writer.writer.writerow(fields)
                def set_fields(row, player, status):
                    sub = player.get_current_subscription()
                    sub_str = sub.to_short_string() if sub is not None else ""
                    row["WSRC Name"] = player.get_ordered_name("utf-8")
                    row["WSRC ID"] = player.pk
                    row["Email"] = player.user.email
                    row["Subscription"] = sub_str
                    row["Status"] = status
                    del db_id_map[player.pk]
                for row in reader:
                    es_id = row["ES ID"]
                    if es_id is None or len(es_id) == 0:
                        continue
                    existing = es_id_map.get(es_id)
                    if existing is not None:
                        set_fields(row, existing, "In Sync")
                    elif row.get("Status") == "Update":
                        db_id = int(row["WSRC ID"])
                        player = db_id_map[db_id]
                        player.england_squash_id = es_id
                        player.save()
                        set_fields(row, player, "Updated - In Sync")
                    else:
                        match = name_map.get(row["Name"])
                        if match is not None:
                            set_fields(row, match, "Name Match - Update Reqd")
                        else:
                            row["Status"] = "No Match"
                    writer.writerow(row)
                leftover = [mem for mem in db_id_map.itervalues() if mem.user.is_active]
                leftover.sort(key=lambda x: x.get_ordered_name())
                for mem in leftover:
                    row = {}
                    set_fields(row, mem, "Missing")
                    writer.writerow(row)
                response = HttpResponse(output.getvalue(), content_type="text/csv")
                response['Content-Disposition'] = 'attachment; filename="es_data.csv"'
                return response

class SubscriptionCostAdmin(SelectRelatedQuerysetMixin, admin.ModelAdmin):
    list_display = ('subscription_type', 'season', 'joining_fee', 'amount')

class SubscriptionTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)


class HasPlayerListFilter(admin.SimpleListFilter):
    "Simple filtering on Player not null"
    title = "Currently Assigned"
    parameter_name = "assigned"
    def lookups(self, request, model_admin):
        return [('y', 'Yes'), ('n', 'No')]
    def queryset(self, request, queryset):
        if self.value():
            today = datetime.date.today()
            ids = [card.pk for card in queryset if card.get_current_ownership_data(today) is not None]
            if self.value() == 'y':
                queryset = queryset.filter(pk__in=ids)
            else:
                queryset = queryset.exclude(pk__in=ids)
        return queryset

class DoorEntryCardAdmin(admin.ModelAdmin):
    search_fields = ('cardnumber',)
    list_select_related = True
    list_display = ('cardnumber', 'is_registered', 'linked_current_owner')
    list_filter = ("is_registered", HasPlayerListFilter)
    list_per_page = 500
    inlines = (DoorCardLeaseInline,)
    def get_queryset(self, request):
        queryset = super(DoorEntryCardAdmin, self).get_queryset(request)
        queryset = queryset.select_related('player__user', 'season')
        queryset = queryset.prefetch_related('doorcardlease_set__player__user')
        return queryset
    def linked_current_owner(self, obj):
        owner = obj.get_current_ownership_data()
        if owner is None:
            return "(None)"
        link = urlresolvers.reverse("admin:usermodel_player_change", args=[owner.player.id])
        return u'<a href="%s">%s</a>' % (link, owner.player.get_ordered_name())
    linked_current_owner.allow_tags = True
    linked_current_owner.short_description = "Currently Assigned To"

class IsCurrentListFilter(admin.SimpleListFilter):
    "Simple filtering on current ownership"
    title = "Returned"
    parameter_name = "returned"
    def lookups(self, request, model_admin):
        return [('y', 'Yes'), ('n', 'No')]
    def queryset(self, request, queryset):
        if self.value() == 'y':
            queryset = queryset.filter(date_returned__isnull=False)
        elif self.value() == 'n':
            queryset = queryset.filter(date_returned__isnull=True)
        return queryset

class DoorCardLeaseAdmin(admin.ModelAdmin):
    search_fields = ('player__user__first_name', 'player__user__last_name', 'card__cardnumber')
    list_display = ('card', 'linked_player', 'current_owner_active', 'date_issued', 'date_returned')
    list_filter = ("card__is_registered", "player__user__is_active", IsCurrentListFilter)
    list_select_related = ('player__user', 'card')
    form = DoorCardLeaseForm
    
    def linked_player(self, obj):
        link = urlresolvers.reverse("admin:usermodel_player_change", args=[obj.player.id])
        return u'<a href="%s">%s</a>' % (link, obj.player.get_ordered_name())
    linked_player.allow_tags = True
    linked_player.short_description = "Assigned To"
    linked_player.admin_order_field = "user__last_name"
    def current_owner_active(self, obj):
        return obj.player.user.is_active
    current_owner_active.boolean = True
    current_owner_active.short_description = "Member Active?"    
    
class EventHasPlayerListFilter(HasPlayerListFilter):
    "Simple filtering on card__player not null"
    title = "Was Assigned"
    def queryset(self, request, queryset):
        if self.value():
            def search(event):
                if event.card is None:
                    return False
                return event.card.get_current_ownership_data(event.received_time.date()) is not None
            ids = [event.pk for event in queryset if search(event)]
            if self.value() == 'y':
                queryset = queryset.filter(pk__in=ids)
            else:
                queryset = queryset.exclude(pk__in=ids)
        return queryset

class DoorEventForm(forms.ModelForm):
    "Override form for more efficient DB interaction"
    queryset = get_related_field_limited_queryset(DoorCardEvent.card.field)
    card = forms.ModelChoiceField(queryset=queryset.select_related("player__user"), required=False)

class DoorCardEventAdmin(admin.ModelAdmin):
    search_fields = ('card__cardnumber',)
    list_display = ('event', 'linked_cardnumber', 'linked_player', 'timestamp', 'received_time')
    list_filter = ("event", EventHasPlayerListFilter)
    form = DoorEventForm

    def get_queryset(self, request):
        queryset = super(DoorCardEventAdmin, self).get_queryset(request)
        queryset = queryset.select_related('card')
        queryset = queryset.prefetch_related('card__doorcardlease_set__player__user')
        return queryset

    def get_search_results(self, request, queryset, search_term):
        search_term_lower = search_term.lower().strip()
        ids = None
        if len(search_term_lower) > 0:
            today = datetime.date.today()
            def search(event):
                if event.card is None:
                    return False
                owner = event.card.get_current_ownership_data(today)
                return owner is not None and search_term_lower in owner.player.user.get_full_name().lower()
            ids = [event.pk for event in queryset.all() if search(event)]
        queryset, use_distinct = super(DoorCardEventAdmin, self).get_search_results(request, queryset, search_term)
        if ids is not None:
            queryset |= self.model.objects.filter(pk__in=ids)
        return queryset, use_distinct
    
    def linked_cardnumber(self, obj):
        if obj.card is None:
            return "(None)"
        link = urlresolvers.reverse("admin:usermodel_doorentrycard_change", args=[obj.card.pk])
        return u'<a href="%s">%s</a>' % (link, obj.card.cardnumber)
        return obj.card.cardnumber
    linked_cardnumber.short_description = "Card Number"
    linked_cardnumber.allow_tags = True
    linked_cardnumber.admin_order_field = "card__cardnumber"

    def linked_player(self, obj):
        lease = None
        if obj.card is not None:
            lease = obj.card.get_current_ownership_data(obj.received_time.date())
        if lease is None:
            return "(None)"
        link = urlresolvers.reverse("admin:usermodel_player_change", args=[lease.player.id])
        return u'<a href="%s">%s</a>' % (link, lease.player.get_ordered_name())
    linked_player.allow_tags = True
    linked_player.short_description = "Assigned To"
    linked_player.admin_order_field = "card__doorcardlease__player__user__last_name"
    
admin.site.register(Season, SeasonAdmin)
admin.site.register(Subscription, SubscriptionAdmin)
admin.site.register(Player, PlayerAdmin)
admin.site.register(SubscriptionCost, SubscriptionCostAdmin)
admin.site.register(SubscriptionType, SubscriptionTypeAdmin)
admin.site.register(DoorEntryCard, DoorEntryCardAdmin)
admin.site.register(DoorCardEvent, DoorCardEventAdmin)
admin.site.register(DoorCardLease, DoorCardLeaseAdmin)
