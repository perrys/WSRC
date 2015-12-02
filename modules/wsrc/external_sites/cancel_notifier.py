#!/usr/bin/python

import datetime
import logging

from django.template import Template, Context
import markdown

from wsrc.utils import timezones, email_utils, text as text_utils
from wsrc.external_sites import evt_filters

FUTURE_CUTTOFF = datetime.timedelta(days=7)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

class Notifier:
  """Emails players when a booking has been cancelled, to allow them to
     book the court. Cancellation events are filtered according to
     criteria that each player specifies, for which times they are
     interested in, etc.
  """

  def __init__(self, current_time=None):
    from wsrc.site.models import EmailContent
    self.userfilters = self.get_configs_from_db(current_time)
    template_obj = EmailContent.objects.get(name="CancellationNotifier")
    self.email_template = Template(template_obj.markup)
    self.send_email = email_utils.send_email

  def process_removed_events(self, removedEvents):

    for event in removedEvents:
      LOGGER.debug("processing {0}".format(event))
      id_list = []  
      # process removed events through the cancelled event notifier:
      for id, userfilter in self.userfilters.iteritems():
        LOGGER.debug("testing filters for player {0}".format(id))
        if userfilter(event):
          LOGGER.debug("matched".format(id))
          id_list.append(id)
      if len(id_list) > 0:
        self.notify(event, id_list)

  def notify(self, event, id_list):
    from wsrc.site.usermodel.models import Player
    players = [Player.objects.get(pk=id) for id in id_list]
    contact_details = [["Name", "E-Mail", "Mobile Phone", "Other Phone"]]
    for player in players:
      contact_details.append([player.get_full_name(), player.user.email, player.cell_phone, player.other_phone])
    context = Context({
      "event": event,
      "content_type": "text/html",
      "notified_members": players,
      "contact_details_table": text_utils.formatTable(contact_details, True)
    })
    subject = "Court Cancellation"
    from_address = "court-cancellations@wokingsquashclub.org"
    html_body = markdown.markdown(self.email_template.render(context))
    context["content_type"] = "text/plain"
    text_body = self.email_template.render(context)
    to_list = [p.user.email for p in players if '@' in p.user.email]
    LOGGER.debug("sending email to {0}".format(to_list))
    try:
      self.send_email(subject, text_body, html_body, from_address, to_list)
    except:
      import traceback
      traceback.print_exc()
  
  def get_configs_from_db(self, current_time):
    from wsrc.site.usermodel.models import Player
    from wsrc.site.models import EventFilter
    userfilters = dict()
    cuttoff_filter = evt_filters.Not(evt_filters.IsFutureEvent(delay=FUTURE_CUTTOFF, now=current_time))
    def get_or_create(id):
      ulist = userfilters.get(id)
      if ulist is None:
        userfilters[id] = ulist = []
      return ulist
    filters = EventFilter.objects.filter(player__user__is_active=True)
    # populate map with lists of event filters keyed by player id
    for filter in filters:
      timefilt = evt_filters.TimeOfDay(filter.earliest, filter.latest)
      days = [o.ordinal for o in filter.days.all()]
      dayfilt = evt_filters.DaysOfWeek(days)
      futurefilt = evt_filters.IsFutureEvent(delay=datetime.timedelta(minutes=filter.notice_period_minutes), now=current_time)
      combined_filter = evt_filters.And([timefilt, dayfilt, futurefilt])
      get_or_create(filter.player.id).append(combined_filter)
    # for each id, convert event filter list into combined filter:
    for id, filters in userfilters.iteritems():
      player = Player.objects.get(pk=id)
      not_userfilt = evt_filters.Not(evt_filters.IsPerson(player.get_full_name()))
      playerfilt = evt_filters.And([not_userfilt, cuttoff_filter, evt_filters.Or(filters)])
      userfilters[id] = playerfilt
    return userfilters
  
if __name__ == "__main__":

  import wsrc.external_sites # call __init__.py
  import unittest

  from wsrc.site.usermodel.models import Player
  from django.contrib.auth.models import User
  from wsrc.site.models import EventFilter, BookingSystemEvent
  import wsrc.utils.collection_utils as utils

  class TestNotifier(Notifier):

    def __init__(self, current_time):
      Notifier.__init__(self, current_time)
      self.recorder = dict()

    def notify(self, event, id_list):
      for id in id_list:
        evt_list = utils.get_or_add(self.recorder, id)
        evt_list.append(event)

  class Tester(unittest.TestCase):
    def setUp(self):
      user = User(username="foobar", first_name="Foo", last_name="Bar", email="foo@bar.com")
      user.save()
      self.player1 = Player(user=user, cell_phone="07123 4567890", other_phone="01234 567890")
      self.player1.save()
      user = User(username="foobaz", first_name="Foo", last_name="Baz", email="foo@baz.com")
      user.save()
      self.player2 = Player(user=user)
      self.player2.save()
    def tearDown(self):
      self.player1.user.delete()
      self.player2.user.delete()
      self.player1.delete()
      self.player2.delete()

    @staticmethod
    def create_filter(player, earliest, latest, notice, days):
      filter = EventFilter(player=player, earliest=earliest, latest=latest, notice_period_minutes=notice)
      filter.save()
      for day in days:
        filter.days.add(day)

    def test_GIVEN_db_WHEN_deserializing_THEN_expected_config_returned(self):
      Tester.create_filter(self.player1, "09:00", "09:30", 270, [6]) # 9-9:30 on saturdays
      Tester.create_filter(self.player1, "19:00", "20:30", 360, [1,2,3,4,5]) # 7-8:30pm weekdays

      notifier = TestNotifier(datetime.datetime(1999,1,1))
      filters = notifier.userfilters.get(self.player1.id)
      self.assertIsNotNone(filters)

      def get_instance_from_list(lst, cls, count=1):
        ntimes=0
        for i in lst:
          if isinstance(i, cls):
            ntimes += 1
            if ntimes == count:
              return i
        self.fail("could not find instance of {cls} in list".format(**locals()))

      self.assertIsInstance(filters, evt_filters.And)
      lst1 = filters.filters
      self.assertEqual(3, len(lst1))

      not_user = get_instance_from_list(lst1, evt_filters.Not)
      self.assertIsInstance(not_user.filter, evt_filters.IsPerson)
      self.assertEqual(not_user.filter.person, self.player1.get_full_name())

      cuttoff = get_instance_from_list(lst1, evt_filters.Not, 2)
      self.assertIsInstance(cuttoff.filter, evt_filters.IsFutureEvent)
      self.assertEqual(FUTURE_CUTTOFF, cuttoff.filter.delay)

      event_filters = get_instance_from_list(lst1, evt_filters.Or)
      event_filters = event_filters.filters
      self.assertEqual(2, len(event_filters))

      def test_filter(filter, player, start_time, end_time, notice, days):
        self.assertIsInstance(filter, evt_filters.And)
        filter_lst = filter.filters
        self.assertEqual(3, len(filter_lst))
        timefilt = get_instance_from_list(filter_lst, evt_filters.TimeOfDay)
        self.assertEqual(datetime.datetime.strptime(start_time, "%H:%M").time(), timefilt.starttime)
        self.assertEqual(datetime.datetime.strptime(end_time,   "%H:%M").time(), timefilt.endtime)
        dayfilt = get_instance_from_list(filter_lst, evt_filters.DaysOfWeek)
        self.assertEqual(days, dayfilt.days)
        noticfilt = get_instance_from_list(filter_lst, evt_filters.IsFutureEvent)
        self.assertEqual(datetime.timedelta(minutes=notice), noticfilt.delay)

      test_filter(event_filters[0], self.player1, "09:00", "09:30", 270, [6])
      test_filter(event_filters[1], self.player1, "19:00", "20:30", 360, [1,2,3,4,5])

    def test_GIVEN_time_range_WHEN_filtering_events_THEN_only_events_within_time_range_returned(self):
      Tester.create_filter(self.player1, "09:00", "10:30", 0, [6]) # 9-10:30 on saturdays
      notifier = TestNotifier(datetime.datetime(1999,1,2,6,0))
      
      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,2,8,59), name="Baz Baz", court=1) # saturday 8:59
      notifier.process_removed_events([removed_event])
      evt_list = notifier.recorder.get(self.player1.id)
      self.assertIsNone(evt_list)
      
      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,2,10,31), name="Baz Baz", court=1) # saturday 10:31
      notifier.process_removed_events([removed_event])
      evt_list = notifier.recorder.get(self.player1.id)
      self.assertIsNone(evt_list)
      
      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,2,9,0), name="Baz Baz", court=1) # saturday 9:00
      notifier.process_removed_events([removed_event])
      evt_list = notifier.recorder.get(self.player1.id)
      self.assertIsNotNone(evt_list)
      self.assertEqual([removed_event], evt_list)

      notifier.recorder.clear()

      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,2,10,30), name="Baz Baz", court=1) # saturday 10:30
      notifier.process_removed_events([removed_event])
      evt_list = notifier.recorder.get(self.player1.id)
      self.assertIsNotNone(evt_list)
      self.assertEqual([removed_event], evt_list)

    def test_GIVEN_day_filter_WHEN_filtering_events_THEN_only_events_on_given_days_returned(self):
      Tester.create_filter(self.player1, "09:00", "10:30", 0, [6]) # 9-10:30 on saturdays
      notifier = TestNotifier(datetime.datetime(1999,1,2,6,0))
      
      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,3,9,15), name="Baz Baz", court=1) # sunday 9:15
      notifier.process_removed_events([removed_event])
      evt_list = notifier.recorder.get(self.player1.id)
      self.assertIsNone(evt_list)
      
      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,2,9,15), name="Baz Baz", court=1) # saturday 9:15
      notifier.process_removed_events([removed_event])
      evt_list = notifier.recorder.get(self.player1.id)
      self.assertIsNotNone(evt_list)
      self.assertEqual([removed_event], evt_list)

    def test_GIVEN_notice_period_WHEN_filtering_events_THEN_only_events_with_enough_notice_returned(self):
      Tester.create_filter(self.player1, "09:00", "12:30", 180, [6]) # 9-12:30 on saturdays, 3hrs notice
      notifier = TestNotifier(datetime.datetime(1999,1,2,8,0)) # saturday 8am
      
      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,2,9,15), name="Baz Baz", court=1) # saturday 9:15
      notifier.process_removed_events([removed_event])
      self.assertIsNone(notifier.recorder.get(self.player1.id))
      
      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,2,12,15), name="Baz Baz", court=1) # saturday 12:15
      notifier.process_removed_events([removed_event])
      evt_list = notifier.recorder.get(self.player1.id)
      self.assertIsNotNone(evt_list)
      self.assertEqual([removed_event], evt_list)

    def test_GIVEN_zero_notice_period_WHEN_filtering_events_THEN_only_future_events_returned(self):
      Tester.create_filter(self.player1, "09:00", "12:30", 0, [6]) # 9-12:30 on saturdays
      notifier = TestNotifier(datetime.datetime(1999,1,2,10,0)) # saturday 10am
      
      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,2,9,15), name="Baz Baz", court=1) # saturday 9:15
      notifier.process_removed_events([removed_event])
      self.assertIsNone(notifier.recorder.get(self.player1.id))

      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,2,10,0), name="Baz Baz", court=1) # saturday 10:00
      notifier.process_removed_events([removed_event])
      self.assertIsNone(notifier.recorder.get(self.player1.id))
      
      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,2,10,1), name="Baz Baz", court=1) # saturday 10:01
      notifier.process_removed_events([removed_event])
      evt_list = notifier.recorder.get(self.player1.id)
      self.assertIsNotNone(evt_list)
      self.assertEqual([removed_event], evt_list)

    def test_GIVEN_event_WHEN_filtering_events_THEN_only_events_within_one_week_returned(self):
      Tester.create_filter(self.player1, "09:00", "12:30", 0, [6]) # 9-12:30 on saturdays
      notifier = TestNotifier(datetime.datetime(1999,1,2,10,0)) # saturday 10am
      
      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,9,10,01), name="Baz Baz", court=1) # next saturday 10:01
      notifier.process_removed_events([removed_event])
      self.assertIsNone(notifier.recorder.get(self.player1.id))

      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,9,10,0), name="Baz Baz", court=1) # next saturday 10:00
      notifier.process_removed_events([removed_event])
      evt_list = notifier.recorder.get(self.player1.id)
      self.assertIsNotNone(evt_list)
      self.assertEqual([removed_event], evt_list)
      notifier.recorder.clear()
      
      removed_event = BookingSystemEvent(start_time=datetime.datetime(1999,1,9,9,59), name="Baz Baz", court=1) # next saturday 09:59
      notifier.process_removed_events([removed_event])
      evt_list = notifier.recorder.get(self.player1.id)
      self.assertIsNotNone(evt_list)
      self.assertEqual([removed_event], evt_list)

    def test_GIVEN_eventlist_WHEN_composing_email_THEN_expected_content_returned(self):
      removed_event = BookingSystemEvent(start_time=datetime.datetime(2099,2,3,20,00), name="Foo Bar", court=2)
      notifier = Notifier(datetime.datetime(2099,2,3))
      def send_email(subject, text_body, html_body, from_address, to_list):
        expected_link = "http://www.court-booking.co.uk/WokingSquashClub/edit_entry_fixed.php?room=2&area=1&hour=20&minute=00&year=2099&month=2&day=3"
        self.assertTrue(expected_link in text_body)
        self.assertTrue(expected_link in html_body)
        self.assertEqual("Court Cancellation", subject)
        self.assertEqual("court-cancellations@wokingsquashclub.org", from_address)
        self.assertEqual([self.player1.user.email], to_list)
      notifier.send_email = send_email
      notifier.notify(removed_event, [self.player1.id])

  unittest.main()

# Local Variables:
# mode: Python
# python-indent-offset: 2
