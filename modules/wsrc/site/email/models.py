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

"Models for control of the email server"

from django.db import models
from django.contrib.auth.models import User

class VirtualDomain(models.Model):
    name = models.CharField(primary_key=True, max_length=255)
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = "Virtual Domain"
        verbose_name_plural = "Virtual Domains"

class VirtualUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT, limit_choices_to=models.Q(is_active=True))
    domain = models.ForeignKey(VirtualDomain, on_delete=models.PROTECT)
    def __unicode__(self):
        return "{0}@{1}".format(self.user.username, self.domain.name)
    class Meta:
        verbose_name = "Virtual User"
        verbose_name_plural = "Virtual Users"
        unique_together = ("user", "domain")
        ordering = ("user__username",)

class VirtualAlias(models.Model):
    from_username = models.CharField("from name", max_length=255)
    from_domain = models.ForeignKey(VirtualDomain, on_delete=models.PROTECT)
    to = models.ForeignKey(VirtualUser, on_delete=models.PROTECT)
    use_user_email = models.BooleanField(default=False)
    def __unicode__(self):
        return "{0}@{1} to {2}".format(self.from_username, self.from_domain.name, self.to)
    class Meta:
        verbose_name = "Virtual Alias"
        verbose_name_plural = "Virtual Aliases"
        unique_together = ("from_username", "from_domain", "to")
        ordering = ("from_username",)
