from django.contrib import admin

from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from wsrc.site.usermodel.models import Player

class PlayerInline(admin.StackedInline):
  model = Player
  can_delete = False
  verbose_name_plural = 'players'

# Define a new User admin
class UserAdmin(UserAdmin):
    inlines = (PlayerInline, )

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
