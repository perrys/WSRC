from django.contrib import admin

from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from wsrc.site.usermodel.models import Player

class UserProfileInline(admin.StackedInline):
 model = Player
 max_num = 1
 can_delete = False

class UserAdmin(AuthUserAdmin):
 inlines = AuthUserAdmin.inlines + [UserProfileInline,]
 list_display = ('username', 'is_active', 'membership_type', 'date_joined_date', 'email', 'first_name', 'last_name', 'cardnumber', 'booking_system_id', 'is_staff')
 list_editable = ("is_active",)

 list_filter = ('player__membership_type', 'is_active', 'is_staff', 'groups', 'is_superuser')
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
