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
import sys
from django.db import transaction

import wsrc.utils.timezones as time_utils
import wsrc.utils.url_utils as url_utils
import scrape_page
import wsrc.site.settings.settings as settings

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
import wsrc.utils.url_utils as url_utils

UK_TZINFO = time_utils.GBEireTimeZone()

class BookingSystemSession:

  LOGIN_PAGE          = "/admin.php"
  BOOKING_PAGE        = "/edit_entry_handler_fixed.php"
  DELETE_BOOKING_PAGE = "/del_entry.php"
  USER_LIST_PAGE      = '/edit_users.php'
  ENTRIES_API         = '/api/entries.php'

  def __init__(self, username=None, password=None):
    self.base_url = url = settings.BOOKING_SYSTEM_ORIGIN
    self.client = url_utils.SimpleHttpClient(url)

    if username is None: # don't attempt to log in if no username supplied.
      return

    self.username = username
    params = {
      "NewUserName" : username, 
      "NewUserPassword" : password,
      "TargetURL" : "admin.php?",
      "Action" : "SetName"
      }
    response = self.client.request(BookingSystemSession.LOGIN_PAGE, params)
    body = response.read()

    if "You are %(username)s" % self.__dict__ not in body:
      status = response.getcode()
      raise Exception("Login failed - username not reported, url: %(url)s, status: %(status)d, body: %(body)s" % locals())

    LOGGER.info("logged in sucessfully." % locals())

  def delete_booking(self, id):
    id = int(id)
    params = {
      "id": id
      }
    response = self.client.get(BookingSystemSession.DELETE_BOOKING_PAGE, params)

    redirections = self.client.redirect_recorder.redirections
    if len(redirections) > 0 and redirections[0][0] == httplib.FOUND:
      LOGGER.info("deleted booking id %(id)d" % locals())
      return

    status = response.getcode()
    body = response.read()
    if body.find("The new booking will conflict") > -1:
      raise Exception("conflict! failed to book court %(court)d@%(timestring)s" % locals())
    raise Exception("unexpected status returned for booking request: %(status)d, response body: %(body)s" % locals())

  def make_booking(self, starttime, court, description=None, name=None):
    """Book a court. STARTTIME is a datetime.datetime object. COURT is
    a court number (1-3). DESCRIPTION, if supplied, is a string. NAME,
    if supplied, will be the shown as the booking name on the booking
    website."""

    if name is None:
      name = self.username

    def parse_datetime(datetime):
      return datetime.year, datetime.month, datetime.day, datetime.hour, datetime.minute

    (year, month, day, hour, minute) = parse_datetime(starttime)
    returnURL = self.base_url + "/day.php?year=%(year)s&month=%(month)s&day=%(day)s&area=1" % locals()
    params = {
      "year" : year,
      "month" : month,
      "day" : day,
      "hour" : hour,
      "minute" : minute,
      "duration" : "45",
      "dur_units" : "minutes",
      "room_id" : str(court),
      "type" : "I",
      "name" : name,
      "create_by" : self.username.lower(),
      "rep_id" : "0",
      "edit_type" : "series",
      "description" : description or "",
      "returl" : returnURL
      }

    timestring = time_utils.as_iso_datetime(starttime)

    response = self.client.get(BookingSystemSession.BOOKING_PAGE, params)
    redirections = self.client.redirect_recorder.redirections
    if len(redirections) > 0 and redirections[0][0] == httplib.FOUND:
      LOGGER.info("booked court %(court)d@%(timestring)s" % locals())
      return

    status = response.getcode()
    body = response.read()
    if body.find("The new booking will conflict") > -1:
      raise Exception("conflict! failed to book court %(court)d@%(timestring)s" % locals())
    raise Exception("unexpected status returned for booking request: %(status)d, response body: %(body)s" % locals())

  def get_week_view(self, date):
    "Retrieve the week view for a given court from the online booking system"
    params = {
      'start_date': date.strftime(time_utils.ISO_DATE_FMT),
      }
    response = self.client.get(BookingSystemSession.ENTRIES_API, params)
    status = response.getcode()
    body = response.read()
    if status != httplib.OK:
      raise Exception("failed to retrieve week view, status: %(status)d, body: %(body)s" % locals())
    return json.loads(body)
    
  def get_booked_courts(self, start_date=None):

    if start_date is None:
      start_date = datetime.date.today()
    from wsrc.site.models import BookingSystemEvent
    bookingSystemEvents = []
    data = self.get_week_view(start_date)
    for date_str, court_data in data.iteritems():
      for court, entries_data in court_data.iteritems():
        for time_str, entry in entries_data.iteritems():
          start_time = datetime.datetime.strptime("{0}T{1}".format(date_str, time_str), "%Y-%m-%dT%H:%M")
          start_time = start_time.replace(tzinfo=time_utils.UK_TZINFO)
          end_time = start_time + datetime.timedelta(minutes=entry["duration_mins"])
          event = BookingSystemEvent(start_time=start_time,
                                     end_time=end_time,
                                     court=court,
                                     name=entry["name"],
                                     event_id=entry["id"],
                                     description=entry["description"])
          bookingSystemEvents.append(event)
          
    return bookingSystemEvents, start_date

  def get_memberlist(self):
    response = self.client.get(BookingSystemSession.USER_LIST_PAGE)
    status = response.getcode()
    body = response.read()
    if status != httplib.OK:
      raise Exception("failed to user list, status: %(status)d, body: %(body)s" % locals())
    return body
    

@transaction.atomic
def sync_db_booking_events(events, start_date, end_date):
  """Sync the db's view of booking events with the given list (usually
     the current state of the booking system) within the range
     START_DATE <= event.start_time < END_DATE. Returns a 3 lists of
     events - newly added events, events which were modified, and
     events which were removed from the booking system since the last
     sync.

  """

  from wsrc.site.models import BookingSystemEvent

  midnight = datetime.time(0, 0, 0, tzinfo=UK_TZINFO)
  existing_events_qs = BookingSystemEvent.objects.all()
  existing_events_qs = existing_events_qs.filter(start_time__gte = datetime.datetime.combine(start_date, midnight))
  existing_events_qs = existing_events_qs.filter(start_time__lt  = datetime.datetime.combine(end_date, midnight))
  existing_events = set(existing_events_qs)

  new_events = []
  modified_events = []

  for evt in events:
    matching_qs = existing_events_qs.filter(start_time=evt.start_time, court=evt.court)
    n_existing = matching_qs.count()
    if n_existing == 0:
      evt.save()
      new_events.append(evt)
    elif n_existing == 1:
      existing_event = matching_qs.first()
      dirty = False
      for prop in ("end_time", "name", "description"):
        if getattr(evt, prop) != getattr(existing_event, prop):
          setattr(existing_event, prop, getattr(evt, prop))
          dirty = True
      if dirty:
        existing_event.save()
        modified_events.append(existing_event)
      existing_events.remove(existing_event)
    else:
      raise Exception("Unexpected duplicate entries with same court/start_time" + str(evt))

  # at the end of the loop, any entries remaining in the
  # existing_events list are ones that have been removed from the
  # booking system
  for evt in existing_events:
    evt.delete()

  return new_events, modified_events, list(existing_events)

if __name__ == "__main__":
  import wsrc.external_sites # call __init__.py
  import unittest

  class MockHttpClient:
    def get(self, selector, params):
      filename = "wsrc/external_sites/test_data/wsrc_{year}-{month}-{day}_court_{room}.html".format(**params)
      class Response():
        def getcode(self):
          return httplib.OK
        def read(self):
          return open(filename).read()
      return Response()

  class Tester(unittest.TestCase):

    def clean_db(self):
      from wsrc.site.models import BookingSystemEvent
      # this test will use the DB. Clear all data before 2000, which we will use for our testing
      old_events = BookingSystemEvent.objects.filter(start_time__lt=datetime.datetime(2000,1,1,0,0))
      old_events.delete()
      self.assertEqual(0, BookingSystemEvent.objects.filter(start_time__lt=datetime.datetime(2000,1,1,0,0)).count())

    def setUp(self):
      self.clean_db()

    def tearDown(self):
      self.clean_db()

    def test_GIVEN_mock_http_client_WHEN_getting_week_view_THEN_something_returned(self):
      session = BookingSystemSession()
      session.client = MockHttpClient()
      html = session.get_week_view(2015, 11, 9, 1)
      self.assertTrue(len(html) > 0)

    def test_GIVEN_mock_http_client_WHEN_scraping_booked_courts_THEN_events_returned_within_date_range(self):
      session = BookingSystemSession()
      session.client = MockHttpClient()
      start_date = datetime.date(2015, 11, 9)
      events, start_date_used = session.get_booked_courts(start_date)
      self.assertTrue(len(events) > 0)
      self.assertEqual(start_date, start_date_used)
      for event in events:
        self.assertTrue(event.start_time.date() >= start_date)
        self.assertTrue(event.start_time.date() <= (start_date + datetime.timedelta(days=14)))
        self.assertTrue(event.end_time >= event.start_time)
        self.assertTrue(event.end_time <= (event.start_time + datetime.timedelta(minutes=180)))
        self.assertTrue(event.court >= 1)
        self.assertTrue(event.court <= 3)

    def test_GIVEN_events_in_db_WHEN_syncing_new_events_THEN_matching_added_modified_removed_returned(self):
      from wsrc.site.models import BookingSystemEvent

      start_date = datetime.date(1999, 1, 4) # 4th Jan 1999 was a monday
      end_date   = datetime.date(1999, 1, 18)
      existing_events = set(BookingSystemEvent.objects.all())
      if len(existing_events) == 0:
        sys.stderr.write("Events DB is empty")

      def create_evt(year, month, day, start_hour, start_minute, duration, court, name, description=None):
        start = datetime.datetime(year, month, day, start_hour, start_minute, tzinfo=UK_TZINFO)
        return BookingSystemEvent(start_time=start, end_time=start+datetime.timedelta(minutes=duration), court=court, name=name, description=description) 

      evt1 = create_evt(1999, 1, 5, 19, 0, 45, 2, "Foo Bar") 
      
      def sync_and_test_expected_numbers(evt_list, expected_added, expected_modified, expected_removed):
        (added, modified, removed) = sync_db_booking_events(evt_list, start_date, end_date)
        self.assertEqual(expected_added,    len(added))
        self.assertEqual(expected_modified, len(modified))
        self.assertEqual(expected_removed,  len(removed))
        return (added, modified, removed)

      # happy day addition test
      (added, modified, removed) = sync_and_test_expected_numbers([evt1], 1, 0, 0)
      self.assertEqual([evt1], added)
      self.assertEqual(len(existing_events)+1, BookingSystemEvent.objects.all().count())

      # do nothing test
      (added, modified, removed) = sync_and_test_expected_numbers([evt1], 0, 0, 0)

      # modification tests

      def test_same_key(modified):
        # The modified event returned is one constructed from the DB
        # copy, so the primary key will be the same but it is a
        # different object from evt1
        self.assertEqual(evt1.pk, modified[0].pk)
        mod_evt = BookingSystemEvent.objects.get(pk=evt1.pk)
        self.assertEqual([mod_evt], modified)

      evt2 = create_evt(1999, 1, 5, 19, 0, 45, 2, "Bar Foo") 
      (added, modified, removed) = sync_and_test_expected_numbers([evt2], 0, 1, 0)
      test_same_key(modified)

      evt3 = create_evt(1999, 1, 5, 19, 0, 90, 2, "Bar Foo") 
      (added, modified, removed) = sync_and_test_expected_numbers([evt3], 0, 1, 0)
      test_same_key(modified)

      evt4 = create_evt(1999, 1, 5, 19, 0, 90, 2, "Bar Foo", description="testing") 
      (added, modified, removed) = sync_and_test_expected_numbers([evt4], 0, 1, 0)
      test_same_key(modified)

      del_evt = BookingSystemEvent.objects.get(pk=evt1.pk)

      # removal test
      (added, modified, removed) = sync_and_test_expected_numbers([], 0, 0, 1)
      for prop in "name", "description", "court", "start_time":        
        self.assertEqual(getattr(del_evt, prop), getattr(removed[0], prop))

  unittest.main()
      
# Local Variables:
# mode: Python
# python-indent-offset: 2


  
  
