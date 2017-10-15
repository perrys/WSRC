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

import hmac

from django.db import models
from django.utils import timezone

import wsrc.site.settings
import wsrc.site.usermodel.models as user_models

class BookingSystemEvent(models.Model):
  start_time = models.DateTimeField(db_index=True)
  end_time = models.DateTimeField()
  court = models.SmallIntegerField()
  name = models.CharField(max_length=64)
  event_id = models.IntegerField(blank=True, null=True)
  description = models.CharField(max_length=128, blank=True, null=True)

  @staticmethod
  def generate_hmac_token(start_time, court):
    msg = "{start_time:%Y-%m-%dT%H:%M}/{court}".format(**locals())
    return hmac.new(wsrc.site.settings.settings.BOOKING_SYSTEM_HMAC_KEY, msg).hexdigest()

  @staticmethod
  def generate_hmac_token_raw(msg):
    return hmac.new(wsrc.site.settings.settings.BOOKING_SYSTEM_HMAC_KEY, msg).hexdigest()

  def hmac_token(self):
    start_time = timezone.localtime(self.start_time)
    return BookingSystemEvent.generate_hmac_token(start_time, self.court)

  def __unicode__(self):
    if self.start_time is None or self.end_time is None:
      return "Invalid event"
    return "{event_id} Court {court} {start_time:%Y-%m-%d %H:%M}-{end_time:%H:%M} {name} \"{description}\"".format(**self.__dict__)



class BookingOffence(models.Model):
  player = models.ForeignKey(user_models.Player)
  OFFENCE_VALUES = (
    ("lc", "Late Cancelation"),
    ("ns", "No Show"),
    )
  offence = models.CharField(max_length=2, choices=OFFENCE_VALUES)
  entry_id = models.IntegerField()
  start_time = models.DateTimeField()
  duration_mins = models.IntegerField()
  court = models.SmallIntegerField()
  name = models.CharField(max_length=64)
  description = models.CharField(max_length=128, blank=True, null=True)
  owner = models.CharField(max_length=64)
  creation_time = models.DateTimeField()
  cancellation_time  = models.DateTimeField(blank=True, null=True)
  rebooked = models.BooleanField(default=False)
  penalty_points = models.SmallIntegerField("Points")
  comment = models.TextField(blank=True, null=True)
  def get_prebook_period(self):
    delta_t = self.start_time - self.creation_time
    if delta_t.days > 0:
      return "{days} day{plural}".format(days=delta_t.days, plural = delta_t.days == 1 and "" or "s")
    hours = delta_t.seconds / 3600
    mins = (delta_t.seconds % 3600) / 60
    return "{hours}h {mins}m".format(**locals())
  def __unicode__(self):
    ctx = {"offence": self.get_offence_display().lower(),
           "name": self.name,
           "start": self.start_time,
           "court": self.court}
    msg = "{start:%Y-%m-%d} {name} court {court} {start:%H:%M} - {offence}".format(**ctx)
    if self.offence == "lc":
      msg += " ({time:%H:%M:%S})".format(time=self.cancellation_time)
    msg += ". Penalty points: {points}".format(points=self.penalty_points)
    return msg
  class Meta:
    verbose_name = "Booking Offence"
    verbose_name_plural = "Booking Offences"
    ordering=["-start_time"]

    
