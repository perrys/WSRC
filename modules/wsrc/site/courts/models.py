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
from django.contrib.auth import models as auth_models

import wsrc.site.settings
import wsrc.site.usermodel.models as user_models
from wsrc.utils.text import obfuscate
from wsrc.utils.timezones import UK_TZINFO, nearest_last_quarter_hour

class BookingSystemEvent(models.Model):
    EVENT_TYPES = (
        ("I", "Member"),
        ("E", "Club"),
    )
    is_active = models.BooleanField(default=True)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    court = models.SmallIntegerField()
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=128, blank=True, null=True)
    event_type = models.CharField(max_length=1, choices=EVENT_TYPES)
    event_id = models.IntegerField(blank=True, null=True)
    no_show = models.BooleanField(default=False)
    no_show_reporter = models.ForeignKey(auth_models.User, blank=True, null=True, limit_choices_to={"is_active": True},
                                         on_delete=models.SET_NULL, related_name="none+")
    created_by = models.ForeignKey(user_models.Player, blank=True, null=True, limit_choices_to={"user__is_active": True},
                                   on_delete=models.SET_NULL)
    created_by_user = models.ForeignKey(auth_models.User, blank=True, null=True, limit_choices_to={"is_active": True},
                                        on_delete=models.SET_NULL, related_name="created_by")
    created_time = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(auth_models.User, blank=True, null=True, limit_choices_to={"is_active": True},
                                        on_delete=models.SET_NULL, related_name="last_updated_by")
    

    
    @classmethod
    def is_writable(cls, created_by_id, user):
        if user is None:
            return False
        if user.is_superuser:
            return True
        return user.pk == created_by_id
        
    def is_writable_by_user(self, user):
        created_by_id = self.created_by_user.pk if self.created_by_user is not None else None
        return self.is_writable(created_by_id, user)
        
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

    @property 
    def in_the_past(self):
        return self.start_time < timezone.now()

    # Properties to emulate a legacy booking system entry:

    @property
    def start_minutes(self):
        start_time = timezone.localtime(self.start_time)
        return start_time.hour * 60 + start_time.minute
        
    @property
    def duration_minutes(self):
        dt = self.end_time - self.start_time
        return int(dt.total_seconds() / 60)

    # Properties to emulate a booking form:
    @property
    def duration(self):
        return datetime.timedelta(minutes=self.duration_minutes)

    @property
    def date(self):
        return self.start_time.date()

    @property
    def booking_id(self):
        if self.created_by is not None:
            return self.created_by.booking_system_id
        return None
    
    @property
    def token(self):
        return self.hmac_token()

    def obfuscated_name(self):
        if self.event_type == "E":
            return self.name
        toks = self.name.split()
        toks = [obfuscate(tok, to_initial=(len(toks)>1 and idx==0)) for idx,tok in enumerate(toks)]
        return " ".join(toks)

    # emulate dictionary API used by JSON events returned from legacy booking system:
    def get(self, key):
        return self.__getitem__(key)
    
    def __contains__(self, key):
        return self.__getitem__(key) is not None

    def __getitem__(self, key):
        "Dictionary access which maps properties from the legacy booking system"
        if key == "start_mins":
            return self.start_minutes
        elif key == "duration_mins":
            return self.duration_minutes
        elif key == "type":
            return self.event_type
        elif key == "id":
            # Return django ID not the booking system one - as this
            # dictionary is intended for use when migrating to the new
            # system:
            return self.pk
        elif key == "created_by":
            player = self.created_by
            if player is None:
                return ""
            return player.user.get_full_name()
        elif key == "timestamp":
            return self.created_time.strftime("%Y-%m-%d %H:%M:%s")
        else:
            return getattr(self, key)

    def validate_unique(self, exclude):
        super(BookingSystemEvent, self).validate_unique(exclude)
        overlap = BookingSystemEvent.objects.filter(is_active=True, court=self.court, start_time__lt=self.end_time, end_time__gt=self.start_time)
        if self.pk:
            overlap = overlap.exclude(pk=self.pk)
        if overlap.count() > 0:
            raise ValidationError("Would conflict with " + unicode(overlap[0]))

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super(BookingSystemEvent, self).save(*args, **kwargs)
        audit = BookingSystemEventAuditEntry.create_from_current(self, is_new=is_new)
        audit.save()

    def delete(self, *args, **kwargs):
        raise Exception("Bookings cannot be deleted, set is_active to False instead")

    def __unicode__(self):
        if self.start_time is None or self.end_time is None:
            return "Invalid event"
        prefix = "[{0}] ".format(self.event_id) if self.event_id is not None else ""
        kwargs = dict(self.__dict__)
        kwargs["start_time"] = timezone.localtime(kwargs["start_time"])
        kwargs["end_time"] = timezone.localtime(kwargs["end_time"])
        return prefix + "Court {court} {start_time:%Y-%m-%d %H:%M}-{end_time:%H:%M} {name} \"{description}\"".format(**kwargs)

    class Meta:
        verbose_name = "Booking"
        ordering = ("-start_time", "-court")

class BookingSystemEventAuditEntry(models.Model):
    booking = models.ForeignKey(BookingSystemEvent)
    UPDATE_TYPES = (
        ("C", "Create"),
        ("U", "Update"),
        ("D", "Delete"),
    )
    update_type = models.CharField(max_length=1, choices=UPDATE_TYPES)
    name = models.CharField(max_length=64)
    description = models.CharField(max_length=128, blank=True, null=True)
    event_type = models.CharField(max_length=1, choices=BookingSystemEvent.EVENT_TYPES)
    updated = models.DateTimeField()
    updated_by = models.ForeignKey(auth_models.User, on_delete=models.PROTECT)

    @classmethod
    def create_from_current(cls, obj, is_new=False):
        if is_new:
            update_type = "C"
        elif obj.is_active:
            update_type = "U"
        else:
            update_type = "D"
        self = cls(update_type=update_type, booking=obj, name=obj.name, description=obj.description, event_type=obj.event_type,
                   updated=obj.last_updated, updated_by=obj.last_updated_by)
        return self

    def __unicode__(self):
        return self.updated.isoformat()
                                             
    class Meta:
        verbose_name = "Booking Audit Entry"
        verbose_name_plural = "Booking Audit Entries"
        ordering = ("-booking__pk", "-updated")

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

    player = models.ForeignKey(user_models.Player, on_delete=models.PROTECT)
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
    player = models.ForeignKey(user_models.Player, on_delete=models.PROTECT)
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

class ClimateMeasurement(models.Model):
    location = models.CharField(max_length=64)
    time = models.DateTimeField()
    temperature = models.FloatField()
    temperature_error = models.FloatField()
    dew_point = models.FloatField()
    dew_point_error = models.FloatField()
    relative_humidity = models.FloatField()
    relative_humidity_error = models.FloatField()
    pressure = models.FloatField(blank=True, null=True)
    pressure_error = models.FloatField(blank=True, null=True)

    def temperature_display(self):
        return u'{0:.1f} \u00B1 {1:.1f}'.format(self.temperature, self.temperature_error)
    temperature_display.short_description = u"Temperature (\u00B0C)"
    temperature_display.admin_order_field = "temperature"
    
    def dew_point_display(self):
        return u'{0:.1f} \u00B1 {1:.1f}'.format(self.dew_point, self.dew_point_error)
    dew_point_display.short_description = u"Dew Point (\u00B0C)"
    dew_point_display.admin_order_field = "dew_point"
    
    def relative_humidity_display(self):
        return u'{0:.0f} \u00B1 {1:.0f}'.format(self.relative_humidity, self.relative_humidity_error)
    relative_humidity_display.short_description = u"Relative Humidity (%)"
    relative_humidity_display.admin_order_field = "relative_humidity"

    def pressure_display(self):
        if self.pressure:
            return u'{0:.1f} \u00B1 {1:.1f}'.format(self.pressure, self.pressure_error)
        return "-"
    pressure_display.short_description = u"Pressure (hPa)"
    pressure_display.admin_order_field = "pressure"

    def __str__(self):
        return "{0:%Y-%m-%d %H:%M%Z} {1}".format(self.time, self.location)

    class Meta:
        unique_together = ("location", "time")
        ordering = ("-time", "location")
        verbose_name = "Climate Measurement"

class CondensationLocation(models.Model):
    name = models.CharField(primary_key=True, max_length=32)
    def __str__(self):
        return self.name
    class Meta:
        ordering = ("name",)
        verbose_name = "Condensation Location"

class CondensationReport(models.Model):
    reporter = models.ForeignKey(user_models.Player, blank=True, null=True, on_delete=models.PROTECT)
    time = models.DateTimeField("Observed Time", default=nearest_last_quarter_hour)
    location = models.ManyToManyField(CondensationLocation)
    comment = models.TextField(blank=True, null=True)

    def get_locations_display(self):
        result = ", ".join([location.pk for location in self.location.all()])
        return result
    get_locations_display.short_description = "Location(s)"

    class Meta:
        ordering = ("-time",)
        verbose_name = "Condensation Report"


    
    
    
        
