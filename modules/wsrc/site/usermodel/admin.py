from django import forms
from django.db import models

from django.contrib import admin

from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from wsrc.site.accounts.models import Transaction
from wsrc.site.usermodel.models import Player, Season, Subscription, SubscriptionPayment
from wsrc.utils.form_utils import SelectRelatedForeignFieldMixin, SelectRelatedQuerysetMixin, CachingModelChoiceField, get_related_field_limited_queryset

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
    
class SubscriptionAdmin(admin.ModelAdmin):
  inlines = (SubscriptionPaymentInline,)
  list_display = ('player', 'season', 'membership_type', 'payment_frequency', 'payments_count', 'total_payments', 'signed_off', "comment")
  list_filter = ('signed_off', 'payment_frequency', 'player__membership_type', )
  list_editable = ('signed_off', 'comment')
  formfield_overrides = {
    models.TextField: {'widget': forms.Textarea(attrs={'cols': 30, 'rows': 1})},
  }
  form = SubscriptionForm

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

admin.site.register(Season, SeasonAdmin)
admin.site.register(Subscription, SubscriptionAdmin)
