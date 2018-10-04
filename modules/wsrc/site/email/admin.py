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

from django import forms
from django.contrib import admin
from .models import VirtualDomain, VirtualUser, VirtualAlias
from wsrc.site.usermodel.models import Player
from wsrc.utils.form_utils import get_related_field_limited_queryset

class VirtualDomainAdmin(admin.ModelAdmin):
    list_display = ("name",)

class UserForm(forms.ModelForm):
    queryset = get_related_field_limited_queryset(VirtualUser.user.field) \
               .order_by("username")
    user = forms.ModelChoiceField(queryset)
    
class VirtualUserAdmin(admin.ModelAdmin):
    list_display = ("user_ordered_name", "domain")
    form = UserForm
    def get_queryset(self, *args, **kwargs):
        return super(VirtualUserAdmin, self).get_queryset(*args, **kwargs).order_by("user__last_name", "user__first_name")
    def user_ordered_name(self, obj):
        return Player.make_ordered_name(obj.user.last_name, obj.user.first_name)
    user_ordered_name.short_description = "User"

class VirtualAliasAdmin(admin.ModelAdmin):
    list_display = ("from_username", "from_domain", "destination")
    list_filter = ("from_username", "from_domain")
    def destination(self, obj):
        email = obj.to.user.email if obj.use_user_email else unicode(obj.to)
        return "{0} [{1}]".format(Player.make_ordered_name(obj.to.user.last_name, obj.to.user.first_name), email)

admin.site.register(VirtualDomain, VirtualDomainAdmin)
admin.site.register(VirtualUser, VirtualUserAdmin)
admin.site.register(VirtualAlias, VirtualAliasAdmin)

