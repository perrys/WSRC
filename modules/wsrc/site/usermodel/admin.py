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

# unregister old user admin
admin.site.unregister(User)
# register new user admin
admin.site.register(User, UserAdmin)
