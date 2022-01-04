#!/usr/bin/python

import csv
import datetime
import json
import logging
import os.path
import re
import sys
import time

from django.db import transaction

import scrape_page
from wsrc.site.usermodel.models import Player
from wsrc.utils import timezones, url_utils

LOGGER = logging.getLogger(__name__)

NAME_PAIRS = [
    ("David", "Dave"),
    ("Michael", "Mike"),
    ("Nicholas", "Nick"),
    ("Philip", "Phil"),
    ("Patrick", "Paddy"),
]


def get_squashlevels_rankings():
    WOKING_SQUASH_CLUB_ID = 6941
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
        "perpage": 200,
    }
    URL = 'https://www.squashlevels.com/players.php'
    AGENT = "SL-client/Woking (+http://www.wokingsquashclub.org)"
    return url_utils.get_content(URL, PARAMS, {"User-Agent": AGENT})


def get_club_fixtures_and_results():
    WOKING_SQUASH_CLUB_ID = 16
    WOKING_SQUASH_CLUB_NAME = "Woking"
    PARAMS = {
        "clubid": WOKING_SQUASH_CLUB_ID,
        "club": WOKING_SQUASH_CLUB_NAME,
    }
    URL = 'http://county.leaguemaster.co.uk/cgi-county/icounty.exe/showclubfixtures'
    return url_utils.get_content(URL, PARAMS)


class PointsTable:

    def __init__(self):
        self.pointsLookup = {7: {2: (3, 0), 3: (3, 0)},  # 7-3 is not valid, assume meant to enter 7-2
                             6: {3: (3, 1), 2: (3, 1), 6: (1, 3)},  # 6-2 is not valid, assume meant to enter 6-3
                             5: {4: (3, 2), 3: (3, 2)},  # 5-3 is not valid, assume meant to enter 6-4
                             4: {4: (2, 2), 3: (2, 1), 2: (2, 0)},
                             3: {3: (1, 1), 2: (1, 0)},
                             2: {2: (0, 0)},
                             }

    def __call__(self, x, y):
        x, y = [int(f) for f in x, y]
        if x > y:
            tup = (x, y)
            reverse = False
        else:
            tup = (y, x)
            reverse = True
        if tup[0] == 999:
            total = (7, 0)
        else:
            total = self.pointsLookup[tup[0]][tup[1]]
        if reverse:
            return (total[1], total[0])
        return total


def analyse_box(data, lookup_table):
    players = [d[0] for d in data]
    rows = [d[1] for d in data]
    matches = []
    for rowidx in range(0, len(rows)):
        for colidx in range(rowidx + 1, len(players)):  # upper-right of triangle
            print str(players[rowidx]) + " vs " + str(players[colidx])
            mypoints = rows[rowidx][colidx]
            if mypoints == "-" or mypoints == "":
                mypoints = None
            if mypoints is not None:
                theirpoints = rows[colidx][rowidx]
                if theirpoints == "-" or theirpoints == "":
                    theirpoints = None
                if theirpoints is not None:
                    print " points: \"%(mypoints)s, %(theirpoints)s\"" % locals()
                    matches.append({"player1": players[rowidx], "player2": players[colidx],
                                    "points": (mypoints, theirpoints),
                                    "scores": lookup_table(mypoints, theirpoints),
                                    })
    return matches, players


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
        last_match_id = row["lastmatchid"]
        player_id = row["playerid"]
        player_name = row["player"]
        events = row["events"]
        level = row["level"]

        try:
            player = Player.objects.get(squashlevels_id=player_id)
        except Player.MultipleObjectsReturned:
            raise Exception("more than one player with same squashlevels id: %d" % player_id)
        except Player.DoesNotExist:
            player = match_player_name(player_name)
            if player is not None:
                player.squashlevels_id = player_id
                player.save()
        datum = SquashLevels(player=player,
                             name=player_name,
                             num_events=events,
                             last_match_date=last_match_date,
                             last_match_id=last_match_id,
                             level=level)
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
                raise Exception("unable to parse row: " + result + " " + str(row))
            points = [int(x) for x in result.split("-")]
            if points[1] > points[0]:  # We won so need highest points first
                swap(points)
        elif result.startswith("Lost"):
            result = result.replace("Lost", "").strip()
            if len(result) > 5:
                raise Exception("unable to parse row: " + result + " " + str(row))
            points = [int(x) for x in result.split("-")]
            if points[0] > points[1]:  # We lost so need lowest points first
                swap(points)

        # games, on the other hand, are always presented from our perspective
        if points[0] is not None:
            games = [int(x) for x in row["Games"].text.split("-")]

        result = LeagueMasterFixtures(
            team=team,
            opponents=opponents,
            home_or_away=venue,
            date=date,
            team1_score=games[0],
            team2_score=games[1],
            team1_points=points[0],
            team2_points=points[1],
            url=row["Match"].link
        )
        result.save()


def cmdline_sync_squashlevels(*args):
    if len(args) > 0:
        data = open(os.path.expanduser(args[0])).read()
    else:
        data = get_squashlevels_rankings()

    json_data = json.loads(data)
    status = json_data.get("status")
    if status is None or status != "good":
        raise Exception(
            "unable to obtain data from squashlevels, status: {0}, json_data: {1}".format(status, str(json_data)))

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


# Local Variables:
# mode: python
# End:
