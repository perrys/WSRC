#!/opt/bin/python

import datetime

UK_TIMEZONE = "Europe/London"

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
  return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")

def naive_utc_to_local(dt, tz):
  dt = dt.replace(tzinfo=UTC_TZINFO)
  dt = dt.astimezone(tz)
