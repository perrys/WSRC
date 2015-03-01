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

from wsrc.utils import jsonutils, timezones
from wsrc.site.usermodel.models import Player

from django.db import transaction

WSRC_CALENDAR_ID = "2pa40689s076sldnb8genvsql8@group.calendar.google.com"
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

NAME_PAIRS = [
  ("David", "Dave"),
  ("Michael", "Mike"),
  ("Nicholas", "Nick"),
  ("Philip", "Phil"),
  ("Patrick", "Paddy"),
]

def get_content(url, params):
  url +=  "?" + urllib.urlencode(params)
  LOGGER.info("Fetching {url}".format(**locals()))
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

def get_old_leage_data(date):
  datefmt = date.strftime("%d%m%y")
  URL = 'http://wokingsquashclub.org/Leagues_%(datefmt)s.htm' % locals()  
  return get_content(URL, {})

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

class PointsTable:

  def __init__(self):
    self.pointsLookup = {7 : {2: (3,0), 3: (3,0)}, # 7-3 is not valid, assume meant to enter 7-2
                         6 : {3: (3,1), 2: (3,1), 6: (1,3)}, # 6-2 is not valid, assume meant to enter 6-3
                         5 : {4: (3,2), 3: (3,2)}, # 5-3 is not valid, assume meant to enter 6-4
                         4 : {4: (2,2), 3: (2,1), 2: (2,0)},
                         3 : {3: (1,1), 2: (1,0)},
                         2 : {2: (0,0)},
                         }
  def __call__(self, x, y):
    x,y = [int(f) for f in x,y]
    if x > y:
      tup = (x,y)
      reverse = False
    else:
      tup = (y,x)
      reverse = True
    if tup[0] == 999:
      total = (7,0)
    else:
      total = self.pointsLookup[tup[0]][tup[1]]
    if reverse:
      return (total[1], total[0])
    return total
  

def analyse_box(name, data):
  if "PREMIER" in name.upper():
    name = "Premier"
  else:
    name = "League " + name[-2:]

  players = [d[0] for d in data if d[0]]
  matches = []
  rowoffset = 0
  coloffset = 1
  table = PointsTable()
  for (rowidx,player) in enumerate(players):
    for colidx in range(rowidx+1,len(players)):
      print players[rowidx] + " vs " + players[colidx]
      mypoints = data[rowidx][colidx+coloffset]
      if mypoints == "-" or mypoints == "": 
        mypoints = None 
      if mypoints is not None:
        theirpoints = data[colidx][rowidx+coloffset]
        if theirpoints == "-" or theirpoints == "": 
          theirpoints = None 
        if theirpoints is not None:
          print " points: \"%(mypoints)s, %(theirpoints)s\"" % locals()
          matches.append({"player1": players[rowidx], "player2": players[colidx], 
                          "points": (mypoints, theirpoints),
                          "scores": table(mypoints, theirpoints),
                          })
  return name, matches, players

def match_player_name(name):
  toks = name.split()
  first = toks[0]
  last = " ".join(toks[1:])
  def trial(first, last):
    return None
  trial_first = first
  idx = 0
  forwards = True
  last_trial = None
  while True:
    if trial_first != last_trial:
      matches = Player.objects.filter(user__first_name__iexact=trial_first, user__last_name__iexact=last)
      if len(matches) == 1:
        return matches[0]
    if idx == len(NAME_PAIRS):
      break 
    pair = NAME_PAIRS[idx]
    last_trial = trial_first
    if forwards:
      trial_first = first.replace(pair[0], pair[1])
      forwards = False
    else:
      trial_first = first.replace(pair[1], pair[0])
      forwards = True
      idx += 1

  LOGGER.error("Unable to find a player matching %(name)s" % locals())
  return None

def update_google_calendar(bookingSystemEvents, clearExistingCalendarEvents=False):

  cal_events.LOGGER.setLevel(logging.DEBUG)

  configDir = os.path.join(os.path.dirname(sys.argv[0]), "..", "etc")
  notifierConfig = jsonutils.deserializeFromFile(open(os.path.join(configDir, "notifier.json")))
  smtpConfig = jsonutils.deserializeFromFile(open(os.path.join(configDir, "smtp.json"))).gmail

  # Obtain all events in the Google calendar starting from the previous Monday:
  date = timezones.nearest_last_monday()
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
  last_match_expr = re.compile("match=(\d+)")
  player_expr = re.compile("player=(\d+)")
  for row in data:
    last_match = row["Last match"]
    last_match_date = datetime.datetime.strptime(last_match.text, "%d %b %Y").date()
    m = last_match_expr.search(last_match.link)
    if m is None:
      raise Exception("unable to find match id in " + last_match.link)
    last_match_id = m.groups()[0]

    player_cell = row["Player"]
    m = player_expr.search(player_cell.link)
    if m is None:
      raise Exception("unable to find player id in " + player_cell.link)
    player_id = m.groups()[0]
    try:
      player = Player.objects.get(squashlevels_id=player_id)
    except Player.MultipleObjectsReturned:
      raise Exception("more than one player with same squashlevels id: %d" % player_id)
    except Player.DoesNotExist:
      player = match_player_name(player_cell.text)
      if player is not None:
        player.squashlevels_id = player_id
        player.save()

    datum = SquashLevels(player          = player,
                         name            = player_cell.text, 
                         num_events      = row["Events"].text,
                         last_match_date = last_match_date, 
                         last_match_id   = last_match_id,
                         level           = row["Level"].text) 
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
  date_expr = re.compile("\d\d/\d\d/\d\d")
  for row in data:
    if "Woking" in row["Away Team"].text:
      venue = "a"
      team = row["Away Team"].text
      opponents = row["Home Team"].text
    else:
      venue = "h"
      team = row["Home Team"].text
      opponents = row["Away Team"].text
    datestr = row["Date"].text
    m = date_expr.search(datestr)
    if m is None:
      raise Exception("unable to find date in " + datestr)
    datestr = datestr[m.start():m.end()]
    date = datetime.datetime.strptime(datestr, "%d/%m/%y").date()

    games = points = [None, None]

    # The leaguemaster page seems to order points inconsistently. We
    # will scrape the Won/Lost field to figure out the correct order.
    result = row["Result"].text
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
      games = [int(x) for x in row["Games"].text.split("-")]

    result = LeagueMasterFixtures(
      team = team,
      opponents = opponents,
      home_or_away = venue,
      date = date,
      team1_score = games[0],
      team2_score = games[1],
      team1_points = points[0],
      team2_points = points[1],
      url = row["Match"].link
      )
    result.save()

@transaction.atomic
def add_old_league_data(boxes_data, end_date):
  from wsrc.site.competitions.models import CompetitionGroup, Competition, Match
  from wsrc.site.usermodel.models import Player

  existing = CompetitionGroup.objects.filter(comp_type="wsrc_boxes", end_date=end_date)
  if len(existing) > 0:
    raise Exception("ERROR - league ending " + end_date.isoformat() + " already exists, delete it first!")

  datefmt = end_date.strftime("%d %B %Y")
  group = CompetitionGroup(name='Leagues Ending %s' % datefmt, comp_type='wsrc_boxes', end_date=end_date, active=False)
  group.save()
  LOGGER.info("Saved CompetitionGroup {group.name} {group.id}".format(**locals()))

  def split_name(name): # works correctly for "Herman van den Berg" :)
    if name == "Diane Benford":
      return "Diane J", "Benford"
    if name == "Michael Davis":
      return "Michael C", "Davis"

    NAME_MAP = {
      "Nick Hiley": "Nicholas Hiley",
      "Phil Peakin": "Philip Peakin",
      "Dave Wooldridge": "David Wooldridge",
      }

    name = name.replace("(jr)", "")
    name = name.strip()
    if name in NAME_MAP:
      name = NAME_MAP[name]

    names = name.split()
    first = names[0]
    last = " ".join(names[1:])
    return first,last

  boxes_data = [analyse_box(*d) for d in boxes_data]

  # look up players first, throw if any are missing
  for name, matches, players in boxes_data:
    player_records = {}
    for player in players:
      first, last = split_name(player)
      try:
        player_records[player] = Player.objects.get(user__first_name=first, user__last_name=last)
      except Exception, e:
        sys.stderr.write("ERROR looking up %(first)s %(last)s - check they exist in DB\n" % locals())
        raise e
    # replace player names with their records:
    del players[:]
    players.extend([(player,record) for player,record in player_records.iteritems()])

  # create a competition for each box and insert players and match scores
  for name, matches, players in boxes_data:
    player_map = dict(players)
    comp = Competition(name=name, end_date=end_date)
    comp.save()
    LOGGER.info("Saved Competition {comp.name} {comp.id}".format(**locals()))
    group.competition_set.add(comp)
    order = 1
    for player_name,record in players:
      comp.entrant_set.create(player=record, ordering=order)
      order += 1
    for match in matches:
      player1 = player_map[match["player1"]]
      player2 = player_map[match["player2"]]
      match_record = Match(competition=comp, team1_player1=player1, team2_player1=player2)
      # we don't know the set scores so just assign 1-0 to the winner of each set
      set = 1
      for i in range(0, match["scores"][0]):
        setattr(match_record, "team1_score%(set)d" % locals(), 1)
        setattr(match_record, "team2_score%(set)d" % locals(), 0)
        set += 1
      for i in range(0, match["scores"][1]):
        setattr(match_record, "team1_score%(set)d" % locals(), 0)
        setattr(match_record, "team2_score%(set)d" % locals(), 1)
        set += 1
      match_record.save()
      group.save()

  
def cmdline_sync_bookings():

  bookingSystemEvents = []
  date = timezones.nearest_last_monday()

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

def cmdline_sync_squashlevels(*args):

  if len(args) > 0:
    data = open(os.path.expanduser(args[0])).read()
  else:
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

def cmdline_add_old_league(*args):
  if len(args) != 1:
    sys.stderr.write("USAGE: %s %s <yyyy-mm-dd>\n" % sys.argv[:2])
    sys.exit(1)
  end_date = timezones.parse_iso_date_to_naive(args[0])
  data = get_old_leage_data(end_date)
  boxes_data = scrape_page.scrape_old_league_table(data)
  add_old_league_data(boxes_data, end_date)
              
        
# Local Variables:
# mode: python
# End:
