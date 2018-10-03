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


from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import BookingSystemEvent
from .cancel_notifier import Notifier

@receiver(post_save, sender=BookingSystemEvent, dispatch_uid="42fd3c1e732611e8a541e512b4beadf4")
def my_handler(sender, *args, **kwargs):
    if kwargs.get("created", False) != True:
        instance = kwargs["instance"]
        if not instance.is_active:
            notifier = Notifier()
            notifier.async_process_removed_events(instance)
