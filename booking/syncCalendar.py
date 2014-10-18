#!/usr/bin/python

import traceback
import datetime
import os.path
import sys
import httplib2
import urllib
import logging

import Calendar
import Scraper

WSRC_CALENDAR_ID = "2pa40689s076sldnb8genvsql8@group.calendar.google.com"
CLEAR_CALENDARS_FIRST = False
LOGGER = logging.getLogger(__name__)

def getWeekView(year, month, day, court):
  "Retrieve the week view for a given court from the online booking system"
  params = {
    'year': str(year),
    'month': "%02d" % month,
    'day': "%02d" % day,
    'area': '1',
    'room': str(court)
    }
  url = 'http://www.court-booking.co.uk/WokingSquashClub/week.php?%s' % urllib.urlencode(params)
  LOGGER.debug("Fetching {url}".format(**locals()))
  h = httplib2.Http()
  (resp_headers, content) = h.request(url, "GET")
  return content

def nearestLastMonday(date=None):
  """Return the Monday previous to DATE, or DATE if it happens to be a Monday. 
  DATE defaults to today if not supplied"""
  if date is None:
    date = datetime.date.today()
  return date - datetime.timedelta(days=date.weekday())

if __name__ == "__main__":

  logging.basicConfig(format='%(asctime)-10s [%(levelname)s] %(message)s',datefmt="%Y-%m-%d %H:%M:%S")
  LOGGER.setLevel(logging.DEBUG)
  Calendar.LOGGER.setLevel(logging.DEBUG)

  # Obtain all events in the Google calendar starting from the previous Monday:
  date = nearestLastMonday()
  cal = Calendar.CalendarWrapper(WSRC_CALENDAR_ID)
  LOGGER.debug("Fetching calendar \"{0}\"".format(WSRC_CALENDAR_ID))
  existingGCalEvents = cal.listEvents(date)
  LOGGER.info("Found {0} event(s) in Google calendar".format(len(existingGCalEvents)))

  if CLEAR_CALENDARS_FIRST:
    for evt in existingGCalEvents:
      cal.deleteEvent(evt)
    existingGCalEvents = []

  # Convert the list of Google calendar events to a dictionary. Events are keyed by start date and location.
  existingGCalEvents = dict([(evt,evt) for evt in existingGCalEvents])

  # Loop over this week and next week:
  for td in (datetime.timedelta(0), datetime.timedelta(days=7)):
    date = date + td
    # Loop over courts 1..3
    for court in range(1,4):
      # Get data from the bookings system for this week and court:
      bookingSystemEventData = getWeekView(date.year, date.month, date.day, court)
      bookingSystemEvents = Scraper.scrapeWeekEvents(bookingSystemEventData, date, "Court %d, Woking Squash Rackets Club, Horsell Moor, Woking, Surrey GU21 4NQ" % court)
      LOGGER.info("Found {0} court booking(s) for court {1} week starting {2}".format(len(bookingSystemEvents), court, date.isoformat()))

      # For each event in the booking system, insert/update in the Google calendar as necessary:
      for evt in bookingSystemEvents:
        try:
          existingEvent = existingGCalEvents.get(evt) # lookup is by start time and location only
          if existingEvent is None:
            # the event does not exist in Google calendar, so add it: 
            cal.addEvent(evt, court) # court number is used for colour ID
          else:
            # an event for the time/location exists, check if it needs updating: 
            if not evt.identicalTo(existingEvent): 
              existingEvent.mergeFrom(evt)
              cal.updateEvent(existingEvent)
            del existingGCalEvents[evt] # remove this event from the list as we have processed it
        except Exception:
          LOGGER.exception("Error processing event %s", evt.__dict__)

  # remove unprocessed Google calendar events. These must have been removed from the booking system since the last sync
  for existingEvent in existingGCalEvents:
    cal.deleteEvent(existingEvent)


