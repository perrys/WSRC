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
import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

import wsrc.site.settings
import wsrc.site.usermodel.models as user_models
from wsrc.utils.text import obfuscate
from wsrc.utils.timezones import UK_TZINFO

class BookingSystemEvent(models.Model):
    EVENT_TYPES = (
        ("I", "Member"),
        ("E", "Club"),
    )
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    court = models.SmallIntegerField()
    name = models.CharField(max_length=64)
    event_type = models.CharField(max_length=1, choices=EVENT_TYPES)
    event_id = models.IntegerField(blank=True, null=True)
    description = models.CharField(max_length=128, blank=True, null=True)
    created_by = models.ForeignKey(user_models.Player, blank=True, null=True, limit_choices_to={"user__is_active": True})
    created_time = models.DateTimeField()
    no_show = models.BooleanField(default=False)

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

    def duration_minutes(self):
        dt = self.end_time - self.start_time
        return int(dt.total_seconds() / 60)

    def in_the_past(self):
        return self.start_time < timezone.now()

    def obfuscated_name(self):
        if self.event_type == "E":
            return self.name
        toks = self.name.split()
        toks = [obfuscate(tok, to_initial=(len(toks)>1 and idx==0)) for idx,tok in enumerate(toks)]
        return " ".join(toks)

    def __unicode__(self):
        if self.start_time is None or self.end_time is None:
            return "Invalid event"
        return "{event_id} Court {court} {start_time:%Y-%m-%d %H:%M}-{end_time:%H:%M} {name} \"{description}\"".format(**self.__dict__)

    class Meta:
        verbose_name = "Booking"


class BookingOffence(models.Model):
    POINT_LIMIT = 11
    POINTS_SYSTEM = [
        {"cancel_period_max": 0, "points": [(0, 6)]},
        {"cancel_period_max": 1, "points": [(18, 4)]},
        {"cancel_period_max": 2, "points": [(18, 3)]},
        {"cancel_period_max": 4, "points": [(18, 2)]},
        {"cancel_period_max": 8, "points": [(18, 1)]},
    ]
    CUTOFF_DAYS = 183

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
    cancellation_time = models.DateTimeField(blank=True, null=True)
    rebooked = models.BooleanField(default=False)
    penalty_points = models.SmallIntegerField("Points")
    comment = models.TextField(blank=True, null=True)
    is_active = models.BooleanField("Active", default=True)
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

    @classmethod
    def get_points(clazz, dt_hours, prebook_hours):
        for pts in clazz.POINTS_SYSTEM:
            if dt_hours <= pts["cancel_period_max"]:
                for (pbh, points) in pts["points"]:
                    if prebook_hours > pbh:
                        return points
                    return 0
        return 0

    @classmethod
    def get_offences_for_player(clazz, player, date=None):
        if date is None:
            date = datetime.date.today() - datetime.timedelta(days=1)
        midnight_today = datetime.datetime.combine(date, datetime.time(0, 0, tzinfo=UK_TZINFO))
        start_date = midnight_today - datetime.timedelta(days=clazz.CUTOFF_DAYS)
        end_date = midnight_today + datetime.timedelta(days=1)
        return clazz.objects.filter(player=player, start_time__gte=start_date, start_time__lt=end_date, is_active=True)

    @classmethod
    def get_total_points_for_player(clazz, player, date=None, total_offences=None):
        if total_offences is None:
            total_offences = clazz.get_offences_for_player(player, date)
        return total_offences.aggregate(models.Sum('penalty_points')).get('penalty_points__sum')

    class Meta:
        verbose_name = "Booking Offence"
        verbose_name_plural = "Booking Offences"
        ordering = ["-start_time"]

class DayOfWeek(models.Model):
    name = models.CharField(max_length=3)
    ordinal = models.IntegerField(unique=True)
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name_plural = "DaysOfTheWeek"
        ordering = ["ordinal"]

class EventFilter(models.Model):
    player = models.ForeignKey(user_models.Player)
    earliest = models.TimeField()
    latest = models.TimeField()
    days = models.ManyToManyField(DayOfWeek, blank=True)
    notice_period_minutes = models.IntegerField("Minimum Notice")
    def clean(self):
        super(EventFilter, self).clean()
        if self.earliest >= self.latest:
            raise ValidationError("Earliest must be prior to latest.")
        
    def __unicode__(self):
        return "EventFilter <%s %s-%s [%s] notice: %s" %\
            (self.player.user.username, self.earliest, self.latest,\
             ",".join([str(d) for d in self.days.all()]), self.notice_period_minutes)
    class Meta:
        verbose_name = "Cancellation Notifier"

