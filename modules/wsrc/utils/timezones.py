#!/opt/bin/python

import datetime

UK_TIMEZONE = "Europe/London"
ISO_DATE_FMT = "%Y-%m-%d"
ISO_TIME_FMT = "%H:%M:%S"
ISO_TIME_MINS_FMT = "%H:%M"
ISO_DATETIME_FMT = "%Y-%m-%dT%H:%M:%S"

class GBEireTimeZone(datetime.tzinfo):

  def __repr__(self):
    return "GB/Eire"

  def tzname(self, dt):
    if self.dst(dt):
      return "BST"
    else:
      return "GMT"

  def utcoffset(self, dt):
    return self.dst(dt)

  # In the UK, DST starts at 1am (standard time) on the last Sunday in March.
  DSTSTART = datetime.datetime(1, 3, 25, 1)
  # and ends at 2am (DST time; 1am standard time) on the last Sunday of Oct.
  # which is the first Sunday on or after Oct 25.
  DSTEND = datetime.datetime(1, 10, 25, 1)

  def dst(self, dt):
    if dt is None or dt.tzinfo is None:
      # An exception may be sensible here, in one or both cases.
      # It depends on how you want to treat them.  The default
      # fromutc() implementation (called by the default astimezone()
      # implementation) passes a datetime with dt.tzinfo is self.
      return datetime.timedelta(0)
    assert dt.tzinfo is self

    # Find first Sunday in April & the last in October.
    start = GBEireTimeZone.first_sunday_on_or_after(GBEireTimeZone.DSTSTART.replace(year=dt.year))
    end   = GBEireTimeZone.first_sunday_on_or_after(GBEireTimeZone.DSTEND.replace(year=dt.year))

    # Can't compare naive to aware objects, so strip the timezone from
    # dt first.
    if start <= dt.replace(tzinfo=None) < end:
      return datetime.timedelta(hours=1)
    else:
      return datetime.timedelta(0)

  @staticmethod
  def first_sunday_on_or_after(dt):
    days_to_go = 6 - dt.weekday()
    if days_to_go:
        dt += datetime.timedelta(days_to_go)
    return dt

UK_TZINFO = GBEireTimeZone()

class UTC(datetime.tzinfo):
  """UTC"""

  def utcoffset(self, dt):
    return datetime.timedelta(0)

  def tzname(self, dt):
    return "UTC"

  def dst(self, dt):
    return datetime.timedelta(0)

UTC_TZINFO = UTC()

def parse_iso_datetime_to_naive(s):
  return datetime.datetime.strptime(s, ISO_DATETIME_FMT)

def parse_iso_date_to_naive(s):
  return datetime.datetime.strptime(s, ISO_DATE_FMT).date()

def as_iso_date(d):
  return d.strftime(ISO_DATE_FMT)

def as_iso_datetime(d):
  return d.strftime(ISO_DATETIME_FMT)

def as_iso_time_mins(d):
  return d.strftime(ISO_TIME_MINS_FMT)

def to_time(minutes):
  return datetime.time(minutes/60, minutes%60)
  

def naive_utc_to_local(dt, tz):
  dt = dt.replace(tzinfo=UTC_TZINFO)
  dt = dt.astimezone(tz)
  return dt

def nearest_last_monday(date=None):
  """Return the Monday previous to DATE, or DATE if it happens to be a Monday. 
  DATE defaults to today if not supplied"""
  if date is None:
    date = datetime.date.today()
  return date - datetime.timedelta(days=date.weekday())

def duration_str(duration):
  mins = int(duration.seconds/60)
  hours = int(mins/60)
  mins  = mins % 60
  result = ""
  from wsrc.utils.text import plural
  if hours > 0:
    result += "{hours} hour{s} ".format(hours=hours, s=plural(hours))
  if mins > 0:
    result += "{mins} min{s}".format(mins=mins, s=plural(mins))
  return result

