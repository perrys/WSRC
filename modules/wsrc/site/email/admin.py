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

from django.contrib import admin
from .models import VirtualDomain, VirtualUser, VirtualAlias

class VirtualDomainAdmin(admin.ModelAdmin):
    list_display = ("name",)

class VirtualUserAdmin(admin.ModelAdmin):
    list_display = ("user", "domain")

class VirtualAliasAdmin(admin.ModelAdmin):
    list_display = ("from_username", "from_domain", "destination")
    list_filter = ("from_username", "from_domain")
    def destination(self, obj):
        if obj.use_user_email:
            return obj.to.user.email
        return unicode(obj.to)

admin.site.register(VirtualDomain, VirtualDomainAdmin)
admin.site.register(VirtualUser, VirtualUserAdmin)
admin.site.register(VirtualAlias, VirtualAliasAdmin)

