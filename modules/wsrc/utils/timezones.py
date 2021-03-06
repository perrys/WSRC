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

"""Date/time utilities with and a UK timezone implementation"""

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
    return datetime.time((minutes/60)%24, minutes%60)

def to_seconds(time):
    return (time.hour * 3600) + (time.minute * 60) + time.second

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

def nearest_last_quarter_hour(epoch=None):
    """Return the time nearest to the given time (defaults to now) on a quarter-hour boundary.
    DATE defaults to today if not supplied"""
    if epoch is None:
        from django.utils import timezone        
        epoch = timezone.now()
    delta_t = datetime.timedelta(minutes=(epoch.minute % 15), seconds=epoch.second, microseconds=epoch.microsecond)
    return epoch - delta_t

def duration_str(duration):
    mins = int(duration.seconds/60)
    hours = int(mins/60)
    mins  = mins % 60
    result = ""
    from wsrc.utils.text import plural
    if hours > 0:
        result += "{hours} hour{s}".format(hours=hours, s=plural(hours))
    if mins > 0:
        if len(result) > 0:
            result += " and "
        result += "{mins} min{s}".format(mins=mins, s=plural(mins))
    return result

def parse_duration(s):
    tokens = s.split()
    seconds = 0
    while len(tokens) >= 2:
        if tokens[0] == "and":
            tokens = tokens[1:]
            continue
        val = int(tokens[0])
        unit = tokens[1]
        if unit.startswith("hour"):
            seconds += val * 3600
        elif unit.startswith("min"):
            seconds += val * 60
        elif unit.startswith("sec"):
            seconds += val
        else:
            raise Exception("Unrecognised unit: \"{unit}\"".format(**locals()))
        tokens = tokens[2:]
    return datetime.timedelta(seconds=seconds)

def create_icalendar_uk_timezone():
    import icalendar
    tzc = icalendar.Timezone()
    tzc.add('tzid', 'Europe/London')
    tzc.add('x-lic-location', 'Europe/London')
    
    tzs = icalendar.TimezoneStandard()
    tzs.add('tzname', 'GMT')
    tzs.add('TZOFFSETFROM', datetime.timedelta(hours=1))
    tzs.add('TZOFFSETTO', datetime.timedelta(hours=0))
    tzs.add('dtstart', datetime.datetime(1970, 10, 25, 2, 0, 0))
    tzs.add('rrule', {'freq': 'yearly', 'bymonth': 10, 'byday': '-1su'})
    
    tzd = icalendar.TimezoneDaylight()
    tzd.add('tzname', 'BST')
    tzd.add('TZOFFSETFROM', datetime.timedelta(hours=0))
    tzd.add('TZOFFSETTO', datetime.timedelta(hours=1))
    tzd.add('dtstart', datetime.datetime(1970, 3, 29, 1, 0, 0))
    tzd.add('rrule', {'freq': 'yearly', 'bymonth': 3, 'byday': '-1su'})
    
    tzc.add_component(tzs)
    tzc.add_component(tzd)
    return tzc

