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
 list_display = ('username', 'is_active', 'email', 'first_name', 'last_name', 'is_staff', 'membership_type', 'booking_system_id')
 list_editable = ("is_active",)

 list_filter = ('player__membership_type', 'is_active', 'is_staff', 'groups', 'is_superuser')
 ordering = ('username', 'first_name', 'last_name')

 def get_queryset(self, request):
  qs = super(UserAdmin, self).get_queryset(request)
  qs = qs.select_related('player')
  return qs
 
 def booking_system_id(self, obj):
  return obj.player.booking_system_id
 booking_system_id.short_description = "Booking Site ID"

 def membership_type(self, obj):
  return obj.player.membership_type
 membership_type.short_description = "Membership Category"

# unregister old user admin
admin.site.unregister(User)
# register new user admin
admin.site.register(User, UserAdmin)
