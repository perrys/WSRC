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

"Manages PHP sessions and common queries from the legacy booking system"

import datetime
import logging
import httplib
import json
import sys
from django.db import transaction

import wsrc.utils.timezones as time_utils
import wsrc.utils.url_utils as url_utils
import wsrc.site.settings.settings as settings

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

UK_TZINFO = time_utils.GBEireTimeZone()

class BookingSystemSession:
    "Manages login and common queries from the booking system"

    LOGIN_PAGE   = "/admin.php"
    BOOKING_PAGE = "/edit_entry_handler_admin.php"
    USERS_API    = "/api/users.php"
    ENTRIES_API  = '/api/entries.php'

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

        LOGGER.info("logged in sucessfully.")

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
        from wsrc.site.courts.models import BookingSystemEvent
        from wsrc.site.usermodel.models import Player
        player_map = dict([(p.booking_system_id, p) for p in Player.objects.all()])
        bookingSystemEvents = []
        data = self.get_week_view(start_date)
        def make_aware_datetime(datetime_str, fmt="%Y-%m-%d %H:%M:%S"):
            the_ts = datetime.datetime.strptime(datetime_str, fmt)
            return the_ts.replace(tzinfo=time_utils.UK_TZINFO)
        if len(data) > 0:
            for date_str, court_data in data.iteritems():
                for court, entries_data in court_data.iteritems():
                    for time_str, entry in entries_data.iteritems():
                        start_time = make_aware_datetime("{0} {1}".format(date_str, time_str), "%Y-%m-%d %H:%M")
                        end_time = start_time + datetime.timedelta(minutes=entry["duration_mins"])
                        event = BookingSystemEvent(start_time=start_time,
                                                   end_time=end_time,
                                                   court=int(court),
                                                   name=entry["name"],
                                                   event_id=entry["id"],
                                                   description=entry["description"],
                                                   event_type=entry["type"],
                                                   created_time=make_aware_datetime(entry["created_ts"]),
                                                   no_show=entry["no_show"],
                        )
                        created_by_id = entry.get("created_by_id")
                        if created_by_id is not None:
                            player = player_map.get(int(created_by_id))
                            if player is not None:
                                event.created_by = player
                        bookingSystemEvents.append(event)

        return bookingSystemEvents, start_date

    def get_memberlist(self):
        response = self.client.get(BookingSystemSession.USERS_API)
        status = response.getcode()
        body = response.read()
        if status != httplib.OK:
            raise Exception("failed to read user list, status: %(status)d, body: %(body)s" % locals())
        return json.loads(body)

    def delete_user_from_booking_system(self, booking_system_id):
        "Permanently delete the given id from the booking system database"
        url = "{url}?id={booking_system_id}".format(url=BookingSystemSession.USERS_API,
                                                   booking_system_id=booking_system_id)
        params = {"method": "DELETE"}
        response = self.client.request(url, params)
        status = response.getcode()
        body = response.read()
        if status != httplib.OK:
            raise Exception("failed to delete user, status: %(status)d, body: %(body)s" % locals())

    def add_user_to_booking_system(self, name, password, email=""):
        "Add the given user details to booking system database"
        url = BookingSystemSession.USERS_API
        params = {"name": name, "password": password, "email": email}
        response = self.client.request(url, params)
        status = response.getcode()
        body = response.read()
        if status != httplib.OK:
            raise Exception("failed to create user, status: {0}, body: {1}".format(status, body))
        return json.loads(body)

    def make_admin_booking(self, date, time, duration_mins, court, name, description, booking_type):
        "Make the given booking using the admin interface - requires admin user credentials"
        url = BookingSystemSession.BOOKING_PAGE
        params = {
            "day": date.day,
            "month": date.month,
            "year": date.year,
            "hour": time.hour,
            "minute": time.minute,
            "duration": duration_mins,
            "dur_units": "minutes",
            "edit_type": "series",
            "type": booking_type,            
            "rooms[]": court,
            "name": name,
            "description": description,
            "create_by": self.username,
            "rep_type": 0,
        }
        self.client.redirect_recorder.clear()
        response = self.client.request(url, params)
        redirections = self.client.redirect_recorder.redirections
        print redirections
        status = redirections[0][0] if len(redirections) > 0 else response.getcode()
        if status != httplib.FOUND:
            body = response.read()
            raise Exception("failed to create booking, status: {0}, body: {1}".format(status, body))

@transaction.atomic
def sync_db_booking_events(events, start_date, end_date):
    """Sync the db's view of booking events with the given list (usually
       the current state of the booking system) within the range
       START_DATE <= event.start_time < END_DATE. Returns a 3 lists of
       events - newly added events, events which were modified, and
       events which were removed from the booking system since the last
       sync.

    """

    from wsrc.site.courts.models import BookingSystemEvent

    midnight = datetime.time(0, 0, 0, tzinfo=UK_TZINFO)
    existing_events_qs = BookingSystemEvent.objects.all()
    existing_events_qs = existing_events_qs.filter(start_time__gte=datetime.datetime.combine(start_date, midnight))
    existing_events_qs = existing_events_qs.filter(start_time__lt=datetime.datetime.combine(end_date, midnight))
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
            for prop in ("end_time", "name", "description", "event_type"):
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
        def __init__(self, selector="wsrc_{start_date}.json"):
            self.selector = selector
        def get(self, selector, params={}):
            filename = ("wsrc/external_sites/test_data/" + self.selector).format(**params)
            class Response():
                def getcode(self):
                    return httplib.OK
                def read(self):
                    return open(filename).read()
            return Response()

    class Tester(unittest.TestCase):

        def clean_db(self):
            from wsrc.site.courts.models import BookingSystemEvent
            # this test will use the DB. Clear all data before 2000, which we will use for our testing
            cutoff = datetime.datetime(2000,1,1,0,0, tzinfo=time_utils.UK_TZINFO)
            old_events = BookingSystemEvent.objects.filter(start_time__lt=cutoff)
            old_events.delete()
            self.assertEqual(0, BookingSystemEvent.objects.filter(start_time__lt=cutoff).count())

        def setUp(self):
            self.clean_db()

        def tearDown(self):
            self.clean_db()

        def test_GIVEN_mock_http_client_WHEN_getting_week_view_THEN_something_returned(self):
            session = BookingSystemSession()
            session.client = MockHttpClient()
            html = session.get_week_view(datetime.date(2015, 11, 9))
            self.assertTrue(len(html) > 0)

        def test_GIVEN_mock_http_client_WHEN_scraping_booked_courts_THEN_events_returned_within_date_range(self):
            session = BookingSystemSession()
            session.client = MockHttpClient()
            start_date = datetime.date(2015, 11, 9)
            events, start_date_used = session.get_booked_courts(start_date)
            self.assertGreater(len(events), 0)
            self.assertEqual(start_date, start_date_used)
            for event in events:
                self.assertGreaterEqual(event.start_time.date(), start_date)
                self.assertLessEqual(event.start_time.date(), (start_date + datetime.timedelta(days=14)))
                self.assertGreaterEqual(event.end_time, event.start_time)
                self.assertLessEqual(event.end_time, (event.start_time + datetime.timedelta(minutes=180)))
                self.assertGreaterEqual(event.court, 1)
                self.assertLessEqual(event.court, 3)

        def test_GIVEN_events_in_db_WHEN_syncing_new_events_THEN_matching_added_modified_removed_returned(self):
            from wsrc.site.courts.models import BookingSystemEvent

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

        def test_GIVEN_mock_http_client_WHEN_getting_user_list_THEN_something_returned(self):
            session = BookingSystemSession()
            session.client = MockHttpClient("users.json")
            user_list = session.get_memberlist()
            self.assertTrue(len(user_list) > 0)
            
    unittest.main()

# Local Variables:
# mode: Python
# python-indent-offset: 2
