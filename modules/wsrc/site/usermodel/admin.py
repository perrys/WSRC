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
    inlines = (UserInline, )

# Re-register UserAdmin
admin.site.register(Player) #, PlayerAdmin)
