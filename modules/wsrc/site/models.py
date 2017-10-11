
import wsrc.site.usermodel.models as user_models
import wsrc.utils.text as text_utils
import hmac

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import wsrc.site.settings

import re

class PageContent(models.Model):
  page = models.CharField(max_length=32)
  markup = models.TextField()
  last_updated = models.DateTimeField(auto_now=True)
  
  def __unicode__(self):
    return self.page

class EmailContent(models.Model):
  TEMPLATE_TYPES = (
    ("django", "Django"),
    ("jinja2", "Jinja 2"),
  )
  name = models.CharField(max_length=32)
  template_type = models.CharField(max_length=16, choices=TEMPLATE_TYPES)
  markup = models.TextField()
  last_updated = models.DateTimeField(auto_now=True)
  
  def __unicode__(self):
    return self.name

class ClubEvent(models.Model):  
  title = models.CharField(max_length=64)
  display_date = models.DateField(blank=True, null=True)
  display_time = models.TimeField(blank=True, null=True)
  picture = models.ImageField(upload_to="event_pictures/%Y/%m/%d", blank=True, null=True)
  markup = models.TextField()
  last_updated = models.DateTimeField(auto_now=True)
  def __unicode__(self):
    date_str = self.display_date is not None and "{display_date:%Y-%m-%d}".format(**self.__dict__) or ""
    return "{title} {date}".format(title=self.title, date=date_str) 

class CommitteeMeetingMinutes(models.Model):
  date = models.DateField()
  pdf_file = models.FileField(("PDF File"), upload_to="actions")
  class Meta:
    verbose_name = "Committee Actions"
    verbose_name_plural = "Committee Actions"
    ordering=["-date"]
  
  
class BookingSystemEvent(models.Model):
  start_time = models.DateTimeField()
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

class SquashLevels(models.Model):
  player = models.ForeignKey(user_models.Player, blank=True, null=True)
  name = models.CharField(max_length=64)
  num_events = models.IntegerField()
  last_match_date = models.DateField()
  last_match_id = models.IntegerField()
  level = models.IntegerField()

class LeagueMasterFixtures(models.Model):
  VENUE_TYPES = (
    ("h", "Home"),
    ("a", "Away"),
    )
  team = models.CharField(max_length=64)
  opponents = models.CharField(max_length=64)
  home_or_away = models.CharField(max_length=1, choices=VENUE_TYPES)
  date = models.DateField()
  team1_score = models.IntegerField(blank=True, null=True)
  team2_score = models.IntegerField(blank=True, null=True)
  team1_points = models.IntegerField(blank=True, null=True)
  team2_points = models.IntegerField(blank=True, null=True)
  url = models.CharField(max_length=128, blank=True, null=True)

class DayOfWeek(models.Model):
  name = models.CharField(max_length=3)
  ordinal = models.IntegerField(unique=True)
  def __unicode__(self):
    return self.name
  class Meta:
    verbose_name_plural = "DaysOfTheWeek"
    ordering=["ordinal"]

class EventFilter(models.Model):
  player = models.ForeignKey(user_models.Player)
  earliest = models.TimeField()
  latest = models.TimeField()
  days = models.ManyToManyField(DayOfWeek, blank=True)
  notice_period_minutes = models.IntegerField("Minimum Notice")
  def __unicode__(self):
    return "EventFilter <%s %s-%s [%s] notice: %s" % (self.player.user.username, self.earliest, self.latest, ",".join([str(d) for d in self.days.all()]), self.notice_period_minutes)

class MaintenanceIssue(models.Model):
  STATUS_VALUES = (
    ("ar", "Awaiting Review"),
    ("aa", "Awaiting Action"),
    ("c", "Complete"),
    ("ni", "Non-issue"),
    )
  reporter = models.ForeignKey(user_models.Player, blank=True, null=True)
  description = models.TextField()
  reported_date = models.DateField(auto_now=True)
  status  = models.CharField(max_length=2, choices=STATUS_VALUES, default="ar")
  target_date = models.DateField(blank=True, null=True)
  comment = models.TextField(blank=True, null=True)
  def __unicode__(self):
    return text_utils.shorten(self.description, 10)


class Suggestion(models.Model):
  suggester = models.ForeignKey(user_models.Player, blank=True, null=True)
  description = models.TextField()
  submitted_date = models.DateField(auto_now=True)
  reviewed_date = models.DateField(blank=True, null=True)
  comment = models.TextField(blank=True, null=True)

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
  rebooked = models.BooleanField()
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
