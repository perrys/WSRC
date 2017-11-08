from django import forms
from django.db import models

from django.contrib import admin

from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from wsrc.site.accounts.models import Transaction
from wsrc.site.usermodel.models import Player, Season, Subscription, SubscriptionPayment
from wsrc.utils.form_utils import SelectRelatedForeignFieldMixin, SelectRelatedQuerysetMixin, CachingModelChoiceField, get_related_field_limited_queryset, PrefetchRelatedQuerysetMixin

class UserProfileInline(admin.StackedInline):
 model = Player
 max_num = 1
 can_delete = False

class UserAdmin(AuthUserAdmin):
 inlines = AuthUserAdmin.inlines + [UserProfileInline,]
 list_display = ('username', 'is_active', 'membership_type', 'date_joined_date', 'email', 'first_name', 'last_name', 'cardnumber', 'booking_system_id', 'is_staff')

 list_filter = ('is_active', 'player__membership_type', 'groups', 'player__prefs_esra_member', 'is_staff', 'is_superuser')
 ordering = ('username', 'first_name', 'last_name')
 list_per_page = 400

 def get_queryset(self, request):
  qs = super(UserAdmin, self).get_queryset(request)
  qs = qs.select_related('player')
  return qs
 
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

 def date_joined_date(self, obj):
  return obj.date_joined.date()
 date_joined_date.short_description = "Joined"
 date_joined_date.admin_order_field = 'date_joined'
 
# unregister old user admin
admin.site.unregister(User)
# register new user admin
admin.site.register(User, UserAdmin)

class SeasonAdmin(admin.ModelAdmin):
  list_display = ('__unicode__', "has_ended")
  list_editable = ("has_ended",)

class SubscriptionForm(forms.ModelForm):
  player = forms.ModelChoiceField(queryset=get_related_field_limited_queryset(Subscription.player.field).select_related("user"))  

class SubscriptionPaymentForm(forms.ModelForm):
  transaction = CachingModelChoiceField(queryset=get_related_field_limited_queryset(SubscriptionPayment.transaction.field))
    
class SubscriptionPaymentInline(SelectRelatedQuerysetMixin, admin.StackedInline):
  model = SubscriptionPayment
  can_delete = True
  form = SubscriptionPaymentForm

class SeasonListFilter(admin.SimpleListFilter):
  title = "Season"
  parameter_name = "season"
  def lookups(self, request, model_admin):
   return [(s.id, unicode(s)) for s in Season.objects.all()]
  def queryset(self, request, queryset):
   if self.value():
     queryset = queryset.filter(season_id=self.value())
   return queryset
  
class SubscriptionAdmin(admin.ModelAdmin):
  inlines = (SubscriptionPaymentInline,)
  list_display = ('player', 'season', 'membership_type', 'payment_frequency', 'payments_count', 'total_payments', 'signed_off', "comment")
  list_filter = (SeasonListFilter, 'signed_off', 'payment_frequency', 'player__membership_type', )
  list_editable = ('signed_off', 'comment')
  formfield_overrides = {
    models.TextField: {'widget': forms.Textarea(attrs={'cols': 30, 'rows': 1})},
  }
  form = SubscriptionForm
  list_per_page = 400

  def subscription(self, obj):
    return unicode(obj)
  subscription.admin_order_field = "player__user__first_name"
  
  def total_payments(self, obj):
    return obj.get_total_payments()
  total_payments.short_description = "Total"

  def membership_type(self, obj):
    return obj.player.membership_type 
  membership_type.short_description = "Membership Type"
  membership_type.admin_order_field = "player__membership_type"
   
  def get_queryset(self, request):
    qs = super(SubscriptionAdmin, self).get_queryset(request)
    qs = qs.select_related('player__user', 'season')
    qs = qs.prefetch_related('payments__transaction')
    return qs

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
      s = Subscription(player=player, season=latest_season, payment_frequency=payment_freq)
      s.save()
update_subscriptions.short_description="Check/update subscriptions"

class PlayerAdmin(SelectRelatedQuerysetMixin, PrefetchRelatedQuerysetMixin, admin.ModelAdmin):
  list_filter = ('user__is_active', 'membership_type', )
  list_display = ('name', 'active', 'membership_type', 'current_season', 'signed_off',
                  'cell_phone', 'other_phone',
                  'cardnumber', 'england_squash_id',
                  'prefs_receive_email', 'prefs_esra_member', 'prefs_display_contact_details')
  search_fields = ('user__first_name', 'user__last_name', 'cardnumber')
  prefetch_related_fields = ('subscription_set__season',)
  list_per_page = 400
  actions = (update_subscriptions,)
  
  def name(self, obj):
    return obj.user.get_full_name()
  name.admin_order_field = 'user__first_name'

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
   
admin.site.register(Season, SeasonAdmin)
admin.site.register(Subscription, SubscriptionAdmin)
admin.site.register(Player, PlayerAdmin)
