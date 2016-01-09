#!/usr/bin/python

import datetime
import json
import logging
import os.path
import sys
import time
import traceback
import re

import scrape_page
import evt_filters
import cancel_notifier

from wsrc.utils import jsonutils, timezones, url_utils
from wsrc.site.usermodel.models import Player

from django.db import transaction

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

NAME_PAIRS = [
  ("David", "Dave"),
  ("Michael", "Mike"),
  ("Nicholas", "Nick"),
  ("Philip", "Phil"),
  ("Patrick", "Paddy"),
]

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
    "format": "json",
    }
  URL = 'http://www.squashlevels.com/players.php'
  AGENT = "SL-client/Woking (+http://www.wokingsquashclub.org)"  
  return url_utils.get_content(URL, PARAMS, {"User-Agent": AGENT})

def get_club_fixtures_and_results():
  WOKING_SQUASH_CLUB_ID=16
  WOKING_SQUASH_CLUB_NAME="Woking"
  PARAMS = {
    "clubid": WOKING_SQUASH_CLUB_ID,
    "club": WOKING_SQUASH_CLUB_NAME,
    }
  URL = 'http://county.leaguemaster.co.uk/cgi-county/icounty.exe/showclubfixtures'
  return url_utils.get_content(URL, PARAMS)

def get_old_leage_data(date):
  datefmt = date.strftime("%d%m%y")
  URL = 'http://wokingsquashclub.org/Leagues_%(datefmt)s.htm' % locals()  
  return url_utils.get_content(URL, {})

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

@transaction.atomic
def update_squash_levels_data(data):
  from wsrc.site.models import SquashLevels

  SquashLevels.objects.all().delete()
  for row in data:
    last_match_date = row["lastmatch_date"]
    last_match_date = time.strftime("%Y-%m-%d", time.localtime(last_match_date))
    last_match_id   = row["lastmatchid"]
    player_id       = row["playerid"]
    player_name     = row["player"]
    events          = row["events"]
    level           = row["level"]

    try:
      player = Player.objects.get(squashlevels_id=player_id)
    except Player.MultipleObjectsReturned:
      raise Exception("more than one player with same squashlevels id: %d" % player_id)
    except Player.DoesNotExist:
      player = match_player_name(player_name)
      if player is not None:
        player.squashlevels_id = player_id
        player.save()
    datum = SquashLevels(player          = player,
                         name            = player_name, 
                         num_events      = events,
                         last_match_date = last_match_date, 
                         last_match_id   = last_match_id,
                         level           = level) 
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

  import wsrc.external_sites.booking_manager as booking_manager

  session = booking_manager.BookingSystemSession()
  events, start_date_used = session.get_booked_courts()
  (new_events, modified_events, removed_events) = booking_manager.sync_db_booking_events(events, start_date_used, start_date_used + datetime.timedelta(days=14))
  LOGGER.info("{0} new bookings, {1} modified, {2} cancelled".format(len(new_events), len(modified_events), len(removed_events)))

  notifier = cancel_notifier.Notifier()
  notifier.process_removed_events(removed_events)
  
def cmdline_sync_squashlevels(*args):

  if len(args) > 0:
    data = open(os.path.expanduser(args[0])).read()
  else:
    data = get_squashlevels_rankings()

  json_data = json.loads(data)
  status = json_data.get("status")
  if status is None or status != "good":
    raise Exception("unable to obtain data from squashlevels, status: {0}, json_data: {1}".format(status, str(json_data)))

  player_data = json_data["data"]
  LOGGER.info("Obtained {0} players from SquashLevels".format(len(player_data)))

  if len(player_data) > 0:
    update_squash_levels_data(player_data)

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
