#!/usr/bin/python

import datetime
import httplib2
import logging
import os.path
import sys
import traceback
import urllib

import cal_events
import scrape_page
import evt_filters
import actions

from wsrc.utils import jsonutils

WSRC_CALENDAR_ID = "2pa40689s076sldnb8genvsql8@group.calendar.google.com"
CLEAR_CALENDARS_FIRST = False
LOGGER = logging.getLogger(__name__)

def get_content(url, params):
  url +=  "?" + urllib.urlencode(params)
  LOGGER.debug("Fetching {url}".format(**locals()))
  h = httplib2.Http()
  (resp_headers, content) = h.request(url, "GET")
  return content

def get_squashlevels_rankings():
  WOKING_SQUASH_CLUB_ID = 60
  SURREY_COUNTY_ID = 24
  PARAMS = {
    "club": WOKING_SQUASH_CLUB_ID,
    "county": SURREY_COUNTY_ID,
    "show": "last12m",
    "matchtype": "all",
    "playercat": "all",
    "playertype": "all",
    "check": 1,
    "limit_confidence": 1,
    }
  URL = 'http://www.squashlevels.com/players.php'
  return get_content(URL, PARAMS)


def get_week_view(year, month, day, court):
  "Retrieve the week view for a given court from the online booking system"
  params = {
    'year': str(year),
    'month': "%02d" % month,
    'day': "%02d" % day,
    'area': '1',
    'room': str(court)
    }
  URL = 'http://www.court-booking.co.uk/WokingSquashClub/week.php?%s'
  return get_content(URL, params)

def nearest_last_monday(date=None):
  """Return the Monday previous to DATE, or DATE if it happens to be a Monday. 
  DATE defaults to today if not supplied"""
  if date is None:
    date = datetime.date.today()
  return date - datetime.timedelta(days=date.weekday())

def run_from_command_line():

  logging.basicConfig(format='%(asctime)-10s [%(levelname)s] %(message)s',datefmt="%Y-%m-%d %H:%M:%S")
  LOGGER.setLevel(logging.DEBUG)
  cal_events.LOGGER.setLevel(logging.DEBUG)

  configDir = os.path.join(os.path.dirname(sys.argv[0]), "..", "etc")
  notifierConfig = jsonutils.deserializeFromFile(open(os.path.join(configDir, "notifier.json")))
  smtpConfig = jsonutils.deserializeFromFile(open(os.path.join(configDir, "smtp.json"))).gmail

  # Obtain all events in the Google calendar starting from the previous Monday:
  date = nearest_last_monday()
  cal = cal_events.CalendarWrapper(WSRC_CALENDAR_ID)
#  cal.testing = True
  LOGGER.debug("Fetching calendar \"{0}\"".format(WSRC_CALENDAR_ID))
  existingGCalEvents = cal.list_events(date)
  LOGGER.info("Found {0} event(s) in Google calendar".format(len(existingGCalEvents)))

  if CLEAR_CALENDARS_FIRST:
    for evt in existingGCalEvents:
      cal.delete_event(evt)
    existingGCalEvents = []

  # Convert the list of Google calendar events to a dictionary. Events are keyed by start date and location.
  existingGCalEvents = dict([(evt,evt) for evt in existingGCalEvents])

  bookingSystemEvents = []

  # Loop over this week and next week:
  for td in (datetime.timedelta(0), datetime.timedelta(days=7)):
    date = date + td
    # Loop over courts 1..3
    for court in range(1,4):
      # Get data from the bookings system for this week and court:
      bookingSystemEventData = get_week_view(date.year, date.month, date.day, court)
      events = scrape_page.scrape_week_events(bookingSystemEventData, date, "Court %d, Woking Squash Rackets Club, Horsell Moor, Woking, Surrey GU21 4NQ" % court)
      LOGGER.info("Found {0} court booking(s) for court {1} week starting {2}".format(len(bookingSystemEvents), court, date.isoformat()))
      bookingSystemEvents.extend([(event, court) for event in events])

  # For each event in the booking system, insert/update in the Google calendar as necessary:
  for (evt, court) in bookingSystemEvents:
    try:
      existingEvent = existingGCalEvents.get(evt) # lookup is by start time and location only
      if existingEvent is None:
        # the event does not exist in Google calendar, so add it: 
        cal.add_event(evt, court) # court number is used for colour ID
      else:
        # an event for the time/location exists, check if it needs updating: 
        if not evt.identical_to(existingEvent): 
          existingEvent.merge_from(evt)
          cal.update_event(existingEvent)
        del existingGCalEvents[evt] # remove this event from the list as we have processed it
    except Exception:
      LOGGER.exception("Error processing event %s", evt.__dict__)

  # unprocessed Google calendar events must have been removed from the booking system since the last sync
  removedEvents = existingGCalEvents

  for userCfg in notifierConfig.config:
    notifier = actions.Notifier(userCfg, smtpConfig)
    for evt in removedEvents:
      notifier(evt)
    notifier.process_all_events()

  for evt in removedEvents:
    cal.delete_event(evt)


if __name__ == "__main__":
  data = get_squashlevels_rankings()
  data = scrape_page.scrape_squashlevels_table(data)
  import pprint
  print pprint.pprint(data)

# Local Variables:
# mode: python
# End:
