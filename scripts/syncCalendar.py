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
CLEAR_CALENDARS_FIRST = True
LOGGER = logging.getLogger(__name__)

def getWeekView(year, month, day, court):
  params = {
    'year': str(year),
    'month': "%02d" % month,
    'day': "%02d" % day,
    'area': '1',
    'room': str(court)
    }
  url = 'http://www.court-booking.co.uk/WokingSquashClub/week.php?%s' % urllib.urlencode(params)
  LOGGER.info("Fetching {url}".format(**locals()))
  h = httplib2.Http()
  (resp_headers, content) = h.request(url, "GET")
  return content

def nearestLastMonday():
  date = datetime.date.today()
  return date - datetime.timedelta(days=date.weekday())

if __name__ == "__main__":

  logging.basicConfig(format='%(asctime)-10s [%(levelname)s] %(message)s',datefmt="%Y-%m-%d %H:%M:%S")
  LOGGER.setLevel(logging.DEBUG)
  Calendar.LOGGER.setLevel(logging.DEBUG)

  date = nearestLastMonday()
  cal = Calendar.CalendarWrapper(WSRC_CALENDAR_ID)
  LOGGER.debug("Fetching calendar \"{0}\"".format(WSRC_CALENDAR_ID))
  existingGCalEvents = cal.listEvents(date)
  LOGGER.info("Found {0} events in calendar".format(len(existingGCalEvents)))

  if CLEAR_CALENDARS_FIRST:
    for evt in existingGCalEvents:
      cal.deleteEvent(evt)
    existingGCalEvents = []
  
  existingGCalEvents = dict([(evt,evt) for evt in existingGCalEvents])

  for td in (datetime.timedelta(0), datetime.timedelta(days=7)):
    date = date + td
    for court in range(1,4):
      bookingSystemEventData = getWeekView(date.year, date.month, date.day, court)
      bookingSystemEvents = Scraper.scrapeWeekEvents(bookingSystemEventData, date, "WSRC Court %d" % court)
      LOGGER.info("Found {0} court bookings for this week".format(len(bookingSystemEvents)))
      for evt in bookingSystemEvents:
        try:
          existingEvent = existingGCalEvents.get(evt)
          if existingEvent is None:
            cal.addEvent(evt, court) # court number used for color ID
          else:
            if not evt.identicalTo(existingEvent):
              existingEvent.mergeFrom(evt)
              cal.updateEvent(existingEvent)
            del existingGCalEvents[evt]
        except Exception:
          traceback.print_exc()
#        sys.exit(0)

  # remove unconsumed existingGCalEvents
  for existingEvent in existingGCalEvents:
    cal.deleteEvent(existingEvent)


