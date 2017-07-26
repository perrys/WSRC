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

import datetime
import logging
import httplib
import json
import operator
import sys
import unittest
import markdown

from django.core.mail import SafeMIMEMultipart, SafeMIMEText

from email.mime.application import MIMEApplication

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

import wsrc.utils.url_utils as url_utils
import wsrc.site.settings.settings as settings

from wsrc.utils.timezones import naive_utc_to_local, as_iso_date
from wsrc.utils.timezones import UK_TZINFO
from wsrc.utils import email_utils

POINTS_SYSTEM = [
  {"max": 0, "points": 6},
  {"max": 1, "points": 5},
  {"max": 2, "points": 4},
  {"max": 3, "points": 3},
  {"max": 6, "points": 2},
  {"max": 12, "points": 1},
]

ANNUAL_POINT_LIMIT = 11
ANNUAL_CUTOFF_DAYS = 183
ADMIN_USERIDS = [3, 5, 400]
                 
def get_points(dt_hours):
  for p in POINTS_SYSTEM:
    if dt_hours <= p["max"]:
      return p["points"]
  return 0

def datetime_parser(dct):
  def parse_date(s, fmt):
      dt = datetime.datetime.strptime(s, fmt)
      return dt.replace(tzinfo=UK_TZINFO)    
  converters = {
    "date": lambda(s): parse_date(s, "%Y-%m-%d").date(),
    "time": lambda(s): parse_date(s, "%H:%M").timetz(),
    "update_timestamp": lambda(s): parse_date(s, "%Y-%m-%d %H:%M:%S"),
  }
  for k, v in dct.items():
    converter = converters.get(k)
    if converter is not None:
      dct[k] = converter(v)
  return dct

class DateTimeEncoder(json.JSONEncoder):
  def default(self, obj):
    if hasattr(obj, "isoformat"):
      return obj.isoformat()
    return json.JSONEncoder.default(self, obj)

def get_audit_table_and_noshows(date):
  params = {"date": "{date:%Y-%m-%d}".format(date=date)}
  def fetch(path):
    url = settings.BOOKING_SYSTEM_ORIGIN + path
    data = url_utils.get_content(url, params)
    return json.loads(data, object_hook=datetime_parser)
  return [fetch(path) for path in (settings.BOOKING_SYSTEM_NOSHOW, settings.BOOKING_SYSTEM_CHANGES)] 

def get_player(booking_id):
  from wsrc.site.usermodel.models import Player
  try:
    return Player.objects.get(booking_system_id=booking_id)
  except Player.DoesNotExist, e:
    return None

def booked_another_court(data, cancelled_item):
  booked_courts = {}
  for item in data:
    if item["entry_id"] == cancelled_item["entry_id"]:
      continue
    if item["update_type"] == "create" and item["update_userid"] == cancelled_item["update_userid"]:
      id = item["entry_id"]
      booked_courts[id] = item
    elif item["update_type"] == "delete":
      id = item["entry_id"]
      if id in booked_courts:
        del booked_courts[id]
  rebooked = len(booked_courts) > 0
  if rebooked:
    LOGGER.info("entry filtered as another court booked: %s", cancelled_item)
  return rebooked

def court_rebooked(data, cancelled_item):
  last_item = None
  for item in data:
    match = True
    for field in ["date", "time", "court"]:
      if item.get(field) != cancelled_item.get(field):
        match = False
        break
    if match:
      last_item = item
  assert(last_item is not None)
  if "delete" == last_item.get("update_type"):
    return False
  return True

def audit_filter(today, data, item): 
  if item["date"] != today:
    return True
  if item["update_type"] != "delete":
    return True
  if booked_another_court(data, item):
    return True
  if item['update_userid'] in ADMIN_USERIDS:
    return True
  return False


def process_audit_table(data, offence_code, player_offence_map, error_list, filter=None):
  import wsrc.site.models as site_models
  processing_noshow = offence_code == "ns"
  def get_or_add(p):
    l = player_offence_map.get(p)
    if l is None:
      player_offence_map[p] = l = []
    return l
  for item in data:
    if filter is not None and filter(item):
      continue
    start_time = datetime.datetime.combine(item["date"], item["time"])
    delta_t_hours = 0
    cancellation_time = item.get("update_timestamp")
    if cancellation_time is not None:
      delta_t_hours = (start_time - cancellation_time).total_seconds() / 3600.0
    user_id = item.get("owner_userid")
    if user_id is None:
      user_id = item.get("update_userid")
    if user_id is None:
      msg = "no user ID supplied for entry #{entry_id} {name} Court {court} @ {date:%Y-%m-%d} {time:%H:%M}, owner \"{owner}\"".format(**item)
      error_list.append({"msg": msg, "data": item})
      LOGGER.warning(msg)      
      continue
    player = get_player(user_id)
    if player is None:
      item["user_id"] = user_id
      msg = "no WSRC user for booking system user #{user_id} for entry #{entry_id} {name} Court {court} @ {date:%Y-%m-%d} {time:%H:%M}".format(**item)
      error_list.append({"msg": msg, "data": item})
      LOGGER.warning(msg)      
      continue
    if 'rebooked' not in item:
      item['rebooked'] = court_rebooked(data, item)
    points = get_points(delta_t_hours)
    offence = site_models.BookingOffence(
      player  = player,
      offence = offence_code,
      entry_id = item["entry_id"],
      start_time = start_time,
      duration_mins = item["duration_mins"],
      court = int(item["court"]),
      name = item["name"],
      description = item["description"],
      owner = item["owner"],
      creation_time = item["created_ts"],
      cancellation_time = cancellation_time,
      rebooked = item['rebooked'],
      penalty_points = points
    )
    offence.save()
    get_or_add(player).append(offence)

def remove_description_updates(audit_table):
  """When a booking description is updated by the old website, it
     creates a new entry and deletes the old one. This function will
     remove those updates from the event table.  """
  def sorter(lhs, rhs):
    r = cmp(*[x["update_timestamp"] for x in (lhs, rhs)])
    if r == 0:
      r = cmp(*[x["update_type"] for x in (lhs, rhs)])
    return r
  audit_table.sort(cmp=sorter)
  events_for_user = dict()
  events_to_remove = []
  for entry in audit_table:
    if entry["update_type"] not in ("create", "delete"):
      continue
    uid = entry["update_userid"]
    slots = events_for_user.get(uid)
    if slots is None:
      slots = events_for_user[uid] = dict()
    slot_time = entry["time"]
    existing = slots.get(slot_time)
    slots[slot_time] = entry
    # if a create preceeds a delete for the same slot with
    # different entry ids then it can only have been done by the old
    # website making an update:
    if existing is not None and \
       entry["update_type"] == "delete" and \
       existing["update_type"] == "create" and \
       entry["entry_id"] != existing["entry_id"] :
      LOGGER.info("removing 2 events as update for %s - %s, %s - %s", existing["owner"], existing["entry_id"], entry["entry_id"], existing["time"].strftime("%H:%M"))
      events_to_remove.append(existing)
      events_to_remove.append(entry)
      slots[slot_time] = None
  for e in events_to_remove:
    audit_table.remove(e)
  return audit_table
    
    

def report_errors(date, errors):
  subject = "Booking Monitor Error"
  from_address = to_address = "webmaster@wokingsquashclub.org"
  text_body, html_body = email_utils.get_email_bodies("BookingMonitorErrors", {"errors": errors, "date": date})
  encoding = settings.DEFAULT_CHARSET
  msg_bodies = SafeMIMEMultipart(_subtype="alternative", encoding=encoding)
  msg_bodies.attach(SafeMIMEText(text_body, "plain", encoding))
  msg_bodies.attach(SafeMIMEText(html_body, "html", encoding))
  attachments = [msg_bodies]
  for error in errors:
    msg = MIMEApplication(json.dumps(error["data"], cls=DateTimeEncoder), "json")
    msg.add_header('Content-Disposition', 'attachment', filename='{id}.json'.format(id=error["data"]["entry_id"]))
    attachments.append(msg)
  
  email_utils.send_email(subject, None, None, from_address, [to_address], extra_attachments=attachments)

def report_offences(date, player, offences, total_offences):
  from django.db.models import Sum
  subject = "Cancelled/Unused Courts - {name} - {date:%Y-%m-%d}".format(name=player.user.get_full_name(), date=date)
  from_address = "booking.monitor@wokingsquashclub.org"
  to_list = [player.user.email or None]
  cc_address = "booking.monitor@wokingsquashclub.org"
  context = {
    "date": date,
    "player": player,
    "offences": offences,
    "total_offences": total_offences,
    "total_points": total_offences.aggregate(Sum('penalty_points')).get('penalty_points__sum'),
    "point_limit": ANNUAL_POINT_LIMIT
  }
  text_body, html_body = email_utils.get_email_bodies("BookingOffenceNotification", context)
  email_utils.send_email(subject, text_body, html_body, from_address, to_list, cc_list=[cc_address])
  
def process_date(date):
  from wsrc.site.models import BookingOffence  
  LOGGER.info("processing date %s", as_iso_date(date))
  
  (noshows, audit_table) = get_audit_table_and_noshows(date)
  for item in noshows:
    item['rebooked'] = False

  remove_description_updates(audit_table)
  filter = lambda(i): audit_filter(date, audit_table, i)

  midnight_today = datetime.datetime.combine(date, datetime.time(0, 0, tzinfo=UK_TZINFO))
  midnight_tomorrow = midnight_today + datetime.timedelta(days=1)
  existing_offences = BookingOffence.objects.filter(start_time__gte=midnight_today, start_time__lt=midnight_tomorrow)
  if existing_offences.count() > 0:
    LOGGER.warning("found %s offence(s) already present for %s, deleting", existing_offences.count(), as_iso_date(date))
    existing_offences.delete()

  player_offence_map = dict()
  errors = list()
  
  process_audit_table(audit_table, "lc", player_offence_map, errors, filter)
  process_audit_table(noshows, "ns", player_offence_map, errors)
  cutoff = midnight_today - datetime.timedelta(days=ANNUAL_CUTOFF_DAYS)
  if len(errors) > 0:
    report_errors(date, errors)
  for player, offences in player_offence_map.items():
    total_offences = BookingOffence.objects.filter(player=player, start_time__gte=cutoff, start_time__lt=midnight_tomorrow)
    report_offences(date, player, offences, total_offences)

class Tester(unittest.TestCase):

  def clean_db(self):
    from wsrc.site.models import BookingOffence  
    # this test will use the DB. Clear all data before 2001, which we will use for our testing
    old_events = BookingOffence.objects.filter(start_time__lt=self.cutoff)
    old_events.delete()
    self.assertEqual(0, BookingOffence.objects.filter(start_time__lt=self.cutoff).count())

  def setUp(self):
    self.date = datetime.date(2001, 1, 1)
    self.cutoff = datetime.datetime.combine(self.date, self.make_uk_time("0:0")) + datetime.timedelta(days=1)
    self.counter = 0;
    self.clean_db()

  def tearDown(self):
    self.clean_db()
    
  def make_uk_time(self, s):
    (hour, minute) = [int(x) for x in s.split(":")]
    return datetime.time(hour, minute, tzinfo=UK_TZINFO)

  def create_entry(self, update_time, time, court, update_type = 'create', entry_id = None, user_id = 4, name = "Foo Bar"):
    if entry_id is None:
      entry_id = self.counter
      self.counter += 1
    date = datetime.date(2001, 1, 1)
    creation_ts = datetime.datetime.combine(date, self.make_uk_time(update_time))
    return {
      'duration_mins': 45,
      'court': court,
      'name': name,
      'update_timestamp': creation_ts,
      'created_ts': creation_ts,
      'update_userid': user_id,
      'update_username': name,
      'owner': name,
      'update_gui': 'booking_website',
      'entry_id': entry_id,
      'update_type': update_type,
      'time': self.make_uk_time(time),
      'date': date,
      'type': 'I',
      'description': ''
    }

  def get_booking_offences(self, **kwargs):
    from wsrc.site.models import BookingOffence
    return BookingOffence.objects.filter(**kwargs)    

  def test_GIVEN_cancelled_entry_WHEN_processing_THEN_offence_registered(self):
    id = 123
    name = "Foo Bar"
    data = [
      self.create_entry("13:00", "19:00", 2, 'delete', entry_id=id, name=name)
    ]
    errors = list()
    player_offence_map = dict()
    process_audit_table(data, 'lc', player_offence_map, errors)
    self.assertEqual(0, len(errors))
    self.assertEqual(1, len(player_offence_map))
    offences = self.get_booking_offences(start_time__lt=self.cutoff)
    self.assertEqual(1, offences.count())
    offence = offences.get(entry_id=id)
    self.assertEqual("lc", offence.offence)
    self.assertEqual(name, offence.owner)
    self.assertEqual(datetime.datetime.combine(self.date, self.make_uk_time("19:00")), offence.start_time)

  def test_GIVEN_deleted_entry_WHEN_filtering_THEN_untouched(self):
    data = [
      self.create_entry("13:00", "19:00", 2, 'delete'),
    ]
    data = [d for d in data if not audit_filter(self.date, data, d)]
    self.assertEqual(1, len(data))

    
  def test_GIVEN_moved_entry_WHEN_filtering_THEN_filtered_out_first_ordering(self):
    data = [
      self.create_entry("13:00", "19:00", 2, 'delete'),
      self.create_entry("13:00", "19:30", 2, 'create'),
      self.create_entry("13:00", "20:15", 2, 'create')
    ]
    data = [d for d in data if not audit_filter(self.date, data, d)]
    self.assertEqual(0, len(data))
    
  def test_GIVEN_moved_entry_WHEN_filtering_THEN_filtered_out_second_ordering(self):
    data = [
      self.create_entry("13:00", "19:30", 2, 'create'),
      self.create_entry("13:00", "19:00", 2, 'delete'),
      self.create_entry("13:00", "20:15", 2, 'create')
    ]
    data = [d for d in data if not audit_filter(self.date, data, d)]
    self.assertEqual(0, len(data))
    
  def test_GIVEN_moved_entry_WHEN_filtering_THEN_filtered_out_third_ordering(self):
    data = [
      self.create_entry("13:00", "19:30", 2, 'create'),
      self.create_entry("13:00", "20:15", 2, 'create'),
      self.create_entry("13:00", "19:00", 2, 'delete'),
    ]
    data = [d for d in data if not audit_filter(self.date, data, d)]
    self.assertEqual(0, len(data))

  def test_GIVEN_random_entries_WHEN_removing_updates_THEN_returned_sorted(self):
    data = [
      self.create_entry("13:02", "19:30", 2, 'create'),
      self.create_entry("13:00", "19:00", 2, 'create'),
      self.create_entry("13:01", "20:15", 2, 'create'),
      self.create_entry("13:01", "20:15", 2, 'delete'),
    ]
    remove_description_updates(data)
    prev = None
    for d in data:
      if prev is not None:
        self.assertGreaterEqual(d["update_timestamp"], prev["update_timestamp"])
      prev = d
    self.assertIsNotNone(prev)
    
  def test_GIVEN_create_delete_pair_WHEN_removing_updates_THEN_removed(self):
    data = [
      self.create_entry("13:01", "19:30", 2, 'create', entry_id=2),
      self.create_entry("13:02", "19:30", 2, 'delete', entry_id=1),
    ]
    remove_description_updates(data)
    self.assertEqual(0, len(data))
    
  def test_GIVEN_create_delete_pair_same_timestamp_WHEN_removing_updates_THEN_removed(self):
    data = [
      self.create_entry("13:01", "19:30", 2, 'delete', entry_id=1),
      self.create_entry("13:01", "19:30", 2, 'create', entry_id=2),
    ]
    remove_description_updates(data)
    self.assertEqual(0, len(data))
    
  def test_GIVEN_create_delete_non_pair_WHEN_removing_updates_THEN_not_removed(self):
    data = [
      self.create_entry("13:01", "19:30", 2, 'create', entry_id=2),
      self.create_entry("13:02", "19:30", 2, 'delete', entry_id=2),
    ]
    remove_description_updates(data)
    self.assertEqual(2, len(data))
    
  def test_GIVEN_change_list_WHEN_checking_rebooked_THEN_positive(self):
    data = [
      self.create_entry("13:01", "19:30", 2, 'create', entry_id=2),
      self.create_entry("13:02", "19:30", 2, 'delete', entry_id=2),
      self.create_entry("13:03", "19:30", 2, 'create', entry_id=3),
    ]
    item = data[0]
    self.assertTrue(court_rebooked(data, item))
    
  def test_GIVEN_change_list_WHEN_checking_rebooked_after_update_THEN_positive(self):
    data = [
      self.create_entry("13:01", "19:30", 2, 'create', entry_id=2),
      self.create_entry("13:02", "19:30", 2, 'delete', entry_id=2),
      self.create_entry("13:03", "19:30", 2, 'create', entry_id=3),
      self.create_entry("13:04", "19:30", 2, 'update', entry_id=3),
    ]
    item = data[0]
    self.assertTrue(court_rebooked(data, item))
    
  def test_GIVEN_change_list_WHEN_checking_rebooked_after_first_delete_THEN_negative(self):
    data = [
      self.create_entry("13:01", "19:30", 2, 'create', entry_id=2),
      self.create_entry("13:02", "19:30", 2, 'delete', entry_id=2),
    ]
    item = data[0]
    self.assertFalse(court_rebooked(data, item))
    
  def test_GIVEN_change_list_WHEN_checking_rebooked_after_second_delete_THEN_negative(self):
    data = [
      self.create_entry("13:01", "19:30", 2, 'create', entry_id=2),
      self.create_entry("13:02", "19:30", 2, 'delete', entry_id=2),
      self.create_entry("13:03", "19:30", 2, 'create', entry_id=3),
      self.create_entry("13:04", "19:30", 2, 'delete', entry_id=3),
    ]
    item = data[0]
    self.assertFalse(court_rebooked(data, item))
if __name__ == "__main__":
  import wsrc.external_sites # call __init__.py
  LOGGER.setLevel(logging.WARNING)
  unittest.main()
  sys.exit(1)
  
  
