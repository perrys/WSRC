
from unittest import *

import wsrc.external_sites # call __init__.py
from wsrc.site.courts.booking_monitor import *

class Tester(unittest.TestCase):

    def clean_db(self):
        from wsrc.site.courts.models import BookingOffence
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

    def get_user(self, user=None, get_first=True):
        if user is None:
            import django.contrib.auth.models as auth_models
            objs = auth_models.User.objects.filter(is_active=True, is_superuser=False)
            user = objs.first() if get_first else objs.last()
        return user

    def create_entry(self, update_time, time, court, update_type = 'C', entry_id = None, user = None, name = None, create_date_offset=0, date_offset=0):
        from wsrc.site.courts.models import BookingSystemEvent, BookingSystemEventAuditEntry
        if entry_id is None:
            entry_id = self.counter
            self.counter += 1
        user = self.get_user(user)
        if name is None:
            name = user.get_full_name()
        date = datetime.date(2001, 1, 1) + datetime.timedelta(days=date_offset)
        start_time  = datetime.datetime.combine(date, self.make_uk_time(time))
        update_ts   = datetime.datetime.combine(date, self.make_uk_time(update_time))
        creation_ts = update_ts + datetime.timedelta(days=create_date_offset)
        booking = BookingSystemEvent(id=entry_id,
                                     start_time=start_time,
                                     end_time=start_time + datetime.timedelta(minutes=45),
                                     court=court,
                                     name=name,
                                     event_type="I",
                                     created_time=creation_ts,
                                     created_by_user=user,
                                     last_updated=update_ts,
                                     last_updated_by=user)
        return BookingSystemEventAuditEntry(update_type=update_type.upper()[0], name=name, event_type=booking.event_type, updated=update_ts, updated_by=user,
                                            booking=booking)

    def get_booking_offences(self, **kwargs):
        from wsrc.site.courts.models import BookingOffence
        return BookingOffence.objects.filter(**kwargs)

    def test_GIVEN_cancelled_entry_WHEN_processing_THEN_offence_registered(self):
        id = 123
        user = self.get_user()
        data = [
          self.create_entry("13:00", "19:00", 2, 'delete', entry_id=id, user=user, create_date_offset=-1)
        ]
        errors = list()
        player_offence_map = dict()
        process_audit_table(data, player_offence_map, errors)
        self.assertEqual(0, len(errors))
        self.assertEqual(1, len(player_offence_map))
        offences = self.get_booking_offences(start_time__lt=self.cutoff)
        self.assertEqual(1, offences.count())
        offence = offences.get(entry_id=id)
        self.assertEqual("lc", offence.offence)
        self.assertEqual(user.get_full_name(), offence.owner)
        self.assertEqual(datetime.datetime.combine(self.date, self.make_uk_time("19:00")), offence.start_time)

    def test_GIVEN_cancelled_entry_WHEN_booked_another_day_THEN_offence_registered(self):
        id = 123
        data = [
          self.create_entry("13:00", "19:00", 2, 'create', entry_id=id-1, date_offset=1),
          self.create_entry("13:00", "19:00", 2, 'delete', entry_id=id,   create_date_offset=-1)
        ]
        filter = lambda(i): audit_filter(data, i)

        user = self.get_user()
        errors = list()
        player_offence_map = dict()
        process_audit_table(data, player_offence_map, errors, filter)
        self.assertEqual(0, len(errors))
        self.assertEqual(1, len(player_offence_map))
        offences = self.get_booking_offences(start_time__lt=self.cutoff)
        self.assertEqual(1, offences.count())
        offence = offences.get(entry_id=id)
        self.assertEqual("lc", offence.offence)
        self.assertEqual(user.get_full_name(), offence.owner)
        self.assertEqual(datetime.datetime.combine(self.date, self.make_uk_time("19:00")), offence.start_time)

    def test_GIVEN_deleted_entry_WHEN_filtering_THEN_untouched(self):
        data = [
          self.create_entry("13:00", "19:00", 2, 'delete'),
        ]
        data = [d for d in data if not audit_filter(data, d)]
        self.assertEqual(1, len(data))


    def test_GIVEN_moved_entry_WHEN_filtering_THEN_filtered_out_first_ordering(self):
        data = [
          self.create_entry("13:00", "19:00", 2, 'delete'),
          self.create_entry("13:00", "19:30", 2, 'create'),
          self.create_entry("13:00", "20:15", 2, 'create')
        ]
        data = [d for d in data if not audit_filter(data, d)]
        self.assertEqual(0, len(data))

    def test_GIVEN_moved_entry_WHEN_filtering_THEN_filtered_out_second_ordering(self):
        data = [
          self.create_entry("13:00", "19:30", 2, 'create'),
          self.create_entry("13:00", "19:00", 2, 'delete'),
          self.create_entry("13:00", "20:15", 2, 'create')
        ]
        data = [d for d in data if not audit_filter(data, d)]
        self.assertEqual(0, len(data))

    def test_GIVEN_moved_entry_WHEN_filtering_THEN_filtered_out_third_ordering(self):
        data = [
          self.create_entry("13:00", "19:30", 2, 'create'),
          self.create_entry("13:00", "20:15", 2, 'create'),
          self.create_entry("13:00", "19:00", 2, 'delete'),
        ]
        data = [d for d in data if not audit_filter(data, d)]
        self.assertEqual(0, len(data))

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

def load_tests(loader, tests, pattern):
    suite = TestSuite()
    tests = loader.loadTestsFromTestCase(Tester)
    suite.addTests(tests)
    return suite
