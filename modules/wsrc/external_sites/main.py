#!/usr/bin/python

import datetime
import httplib2
import logging
import os.path
import sys
import traceback
import urllib
import re

import cal_events
import scrape_page
import evt_filters
import actions

from wsrc.utils import jsonutils

from django.db import transaction

WSRC_CALENDAR_ID = "2pa40689s076sldnb8genvsql8@group.calendar.google.com"
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

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

def get_club_fixtures_and_results():
  WOKING_SQUASH_CLUB_ID=16
  WOKING_SQUASH_CLUB_NAME="Woking"
  PARAMS = {
    "clubid": WOKING_SQUASH_CLUB_ID,
    "club": WOKING_SQUASH_CLUB_NAME,
    }
  URL = 'http://county.leaguemaster.co.uk/cgi-county/icounty.exe/showclubfixtures'
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

def update_google_calendar(bookingSystemEvents, clearExistingCalendarEvents=False):

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

  if clearExistingCalendarEvents:
    for evt in existingGCalEvents:
      cal.delete_event(evt)
    existingGCalEvents = []

  # Convert the list of Google calendar events to a dictionary. Events are keyed by start date and location.
  existingGCalEvents = dict([(evt,evt) for evt in existingGCalEvents])

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

  # process removed events through the cancelled event notifier:
  for userCfg in notifierConfig.config:
    notifier = actions.Notifier(userCfg, smtpConfig)
    for evt in removedEvents:
      notifier(evt)
    notifier.process_all_events()

  for evt in removedEvents:
    cal.delete_event(evt)

@transaction.atomic
def update_booking_events(events):
  from wsrc.site.models import BookingSystemEvent
  BookingSystemEvent.objects.all().delete()
  for (evt, court) in events:
    entry = BookingSystemEvent(
      start_time = evt.time,
      end_time   = evt.time + evt.duration,
      description = evt.name,
      court = court,
      )
    entry.save()
  
@transaction.atomic
def update_squash_levels_data(data):
  from wsrc.site.models import SquashLevels

  SquashLevels.objects.all().delete()
  for row in data:
    datum = SquashLevels(name=row["Player"], 
                         category=row["Category"], 
                         num_events=row["Events"],
                         level=row["Level"]) 
    datum.save()

@transaction.atomic
def update_leaguemaster_data(data):

  def swap(tup):
    t = tup[0]
    tup[0] = tup[1]
    tup[1] = t

  # remove all leaguemaster data
  from wsrc.site.models import LeagueMasterFixtures
  LeagueMasterFixtures.objects.all().delete()

  # process and update. Our team is always the first and we record
  # separately if it was a home or away match.
  for row in data:
    if "Woking" in row["Away Team"]:
      venue = "a"
      team = row["Away Team"]
      opponents = row["Home Team"]
    else:
      venue = "h"
      team = row["Home Team"]
      opponents = row["Away Team"]
    date = row["Date"]
    re_expr = re.compile("\d\d/\d\d/\d\d")
    m = re_expr.search(row["Date"])
    if m is None:
      raise Exception("unable to find date in " + row["Date"])
    datestr = row["Date"][m.start():m.end()]
    date = datetime.datetime.strptime(datestr, "%d/%m/%y").date()

    games = points = [None, None]

    # The leaguemaster page seems to order points inconsistently. We
    # will scrape the Won/Lost field to figure out the correct order.
    result = row["Result"].strip()
    if result.startswith("Won"):
      result = result.replace("Won", "").strip()
      if len(result) > 5:
        raise Exception("unable to parse row: " +result + " " + str(row))
      points = [int(x) for x in result.split("-")]
      if points[1] > points[0]: # We won so need highest points first
        swap(points)
    elif result.startswith("Lost"):
      result = result.replace("Lost", "").strip()
      if len(result) > 5:
        raise Exception("unable to parse row: " +result + " " + str(row))
      points = [int(x) for x in result.split("-")]
      if points[0] > points[1]: # We lost so need lowest points first
        swap(points)

    # games, on the other hand, are always presented from our perspective
    if points[0] is not None:
      games = [int(x) for x in row["Games"].split("-")]

    result = LeagueMasterFixtures(
      team = team,
      opponents = opponents,
      home_or_away = venue,
      date = date,
      team1_score = games[0],
      team2_score = games[1],
      team1_points = points[0],
      team2_points = points[1]
      )
    result.save()

def cmdline_sync_bookings():

  bookingSystemEvents = []
  date = nearest_last_monday()

  # Loop over this week and next week:
  for td in (datetime.timedelta(0), datetime.timedelta(days=7)):
    date = date + td
    # Loop over courts 1..3
    for court in range(1,4):
      # Get data from the bookings system for this week and court:
      bookingSystemEventData = get_week_view(date.year, date.month, date.day, court)
      events = scrape_page.scrape_week_events(bookingSystemEventData, date, court)
      LOGGER.info("Found {0} court booking(s) for court {1} week starting {2}".format(len(bookingSystemEvents), court, date.isoformat()))
      bookingSystemEvents.extend([(event, court) for event in events])

  update_booking_events(bookingSystemEvents)
  update_google_calendar(bookingSystemEvents)

def cmdline_sync_squashlevels():

  data = get_squashlevels_rankings()
  data = scrape_page.scrape_squashlevels_table(data)

  LOGGER.info("Obtained {0} players from SquashLevels".format(len(data)))

  if len(data) > 0:
    update_squash_levels_data(data)

def cmdline_sync_leaguemaster(*args):

  if len(args) > 0:
    data = open(os.path.expanduser(args[0])).read()
  else:
    data = get_club_fixtures_and_results()
  data = scrape_page.scrape_fixtures_table(data)

  LOGGER.info("Obtained {0} fixtures from LeagueMaster".format(len(data)))

  if len(data) > 0:
    update_leaguemaster_data(data)

        
# Local Variables:
# mode: python
# End:
