from django.contrib import admin

from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from wsrc.site.usermodel.models import Player

class UserInline(admin.StackedInline):
  model = User
  can_delete = False

# Define a new User admin
class PlayerAdmin(admin.ModelAdmin):
#    inlines = (UserInline, )
    list_display = (lambda obj: obj.get_full_name(), "membership_type", "cell_phone", "other_phone")
    list_editable = ("membership_type", "cell_phone", "other_phone")
    search_fields = ("user__first_name", "user__last_name")
    readonly_fields = ("full_name",)
    fields = ("full_name", "cell_phone", "other_phone", "short_name", "membership_type", "membership_id", "squashlevels_id", "prefs_receive_email")
    def full_name(self, obj):
      return obj.get_full_name()
# Re-register UserAdmin
admin.site.register(Player, PlayerAdmin)
