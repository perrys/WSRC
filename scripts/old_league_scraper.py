#!/usr/bin/python

import logging
import sys
import os.path
from bs4 import BeautifulSoup
import re
import datetime

NAME_MAPPINGS = {
  "Nick Hiley": "Nicholas Hiley",
  "Mike Rivers": "Michael Rivers",
  "Matt O'Connor": "Matt Oconnor",
  u"Jo\xe3o Marques": "Joao Marques",
  "David Wooldridge": "Dave Wooldridge",
}

class PointsTable:

  def __init__(self):
    self.pointsLookup = {7 : {2: (3,0)},
                         6 : {3: (3,1), 2: (2,0)},
                         5 : {4: (3,2)},
                         4 : {4: (2,2), 3: (2,1), 2: (1,0)},
                         3 : {3: (1,1)},
                         2 : {2: (0,0)},
                         }
  def __call__(self, x, y):
    # fix bad inputs:
    if x == "7": y = 2
    if y == "7": x = 2
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
  
def split_name(name):
  names = name.split()
  first = names[0]
  last = " ".join(names[1:])
  return first,last

def get_usermapping():
  fh = open("../docs/BookingSystemContact.txt")
  result = dict()
  for line in fh:
    toks = line.split("\t")
    if len(toks) > 1 and toks[1]:
      if toks[1] in ("Admin", "Club", "Webmaster"):
        continue
      if toks[1] == "Kerryn":
        toks[1] = "Kerryn Bartlett"
      first,last = split_name(toks[1])
    result[toks[1]] = {"first_name": first, "last_name": last, "email": toks[2], "phone": toks[3], "mobile": toks[4]}
  return result

BOOKING_CONTACTS = get_usermapping()

class CellPredicate:
  def __init__(self, tag):
    self.tag = tag
  def __call__(self, x):
    return hasattr(x, "name") and x.name == self.tag


def tag_generator(head, next_func=lambda(x): x.next_sibling, filt=lambda(x): hasattr(x, "name")):
  """Generator for tag collections. 
  HEAD is the first element in the collection
  NEXT_FUNC provides the next element given the current one
  FILT is a filter function; return False to reject the current element and move to the next
  """
  while head is not None:
    if filt(head):
      yield head
    head = next_func(head)

def count_backwards_tds(tag):
  return len([x for x in tag_generator(tag, next_func=lambda(x): x.previous_sibling, filt=CellPredicate('td'))])

def process_header(tag):
  tg = tag_generator(tag, filt=CellPredicate('td'))
  tg.next()
  nexttag = tg.next()
  league_name = tag.text + " " + nexttag.text
  
  xposition = count_backwards_tds(tag)
  if xposition > 10:
    xposition -= 2
  row_iter = tag_generator(tag.parent, filt=CellPredicate('tr'))
  row_iter.next()
  data_rows = []
  for i in range(0,6):
    row = row_iter.next()
    first = row.find('td')
    col_iter = tag_generator(first, filt=CellPredicate('td'))
    for j in range(0, xposition):
      col_iter.next()
    data_cols = []
    data_rows.append(data_cols)
    details = None
    for j in range(0,8):
      text = col_iter.next().text
      text = text.replace(" (jr)", "").replace(u'\xa0', "")
      if text in NAME_MAPPINGS:
        text = NAME_MAPPINGS[text]
      if text in BOOKING_CONTACTS:
        details = BOOKING_CONTACTS[text]
      data_cols.append(text)
    data_cols.append(details)
  return (league_name, data_rows)

def analyse_box(league_data):
  name,data = league_data
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
      mypoints = data[rowidx][colidx+coloffset]
      if mypoints:
        theirpoints = data[colidx][rowidx+coloffset]
#        print players[rowidx] + " vs " + players[colidx]
        matches.append({"player1": players[rowidx], "player2": players[colidx], 
                        "points": (mypoints, theirpoints),
                        "scores": table(mypoints, theirpoints),
                        })
  return name, matches, players

if __name__ == "__main__":
  infile = sys.stdin
  if len(sys.argv) > 1:
    infile = open(os.path.expanduser(sys.argv[1]))
  soup = BeautifulSoup(infile, "lxml")

  headers = soup.find_all('td', text=re.compile("^League\s+No"))
  leagues = [process_header(h) for h in headers]
  if sys.argv[2] == "players":
    players = [x[1] for x in leagues]
    players = [(item[0],item[-1]) for sublist in players for item in sublist]
    players = [p for p in players if p[0]]
    print players
  elif sys.argv[2] == "boxes":
    end_date = sys.argv[3]
    box_matches = [analyse_box(box) for box in leagues]
    print """
import wsrc.site.competitions.models as comp_models
import wsrc.site.usermodel.models as user_models
"""
    date = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    datefmt = date.strftime("%d %B %Y")
    
    print "group = comp_models.CompetitionGroup(name='Leagues Ending %s', comp_type='wsrc_boxes', end_date='%s', active=False)" % (datefmt, end_date)
    print "group.save()"
    for name, data, players in box_matches:
      print "comp = comp_models.Competition(name='%s', end_date='%s')" % (name, end_date)
      print "comp.save()"
      print "group.competitions.add(comp)"
      for player in players:
        print "player = user_models.Player.objects.get(user__first_name='%s', user__last_name='%s')" % split_name(player)
        print "comp.players.add(player)"
      for match in data:
        print "player1 = user_models.Player.objects.get(user__first_name='%s', user__last_name='%s')" % split_name(match["player1"])
        print "player2 = user_models.Player.objects.get(user__first_name='%s', user__last_name='%s')" % split_name(match["player2"])
        print "match = comp_models.Match(competition=comp, team1_player1=player1, team2_player1=player2)"
        set = 1
        for i in range(0, match["scores"][0]):
          print "match.team1_score%(set)d = 1" % locals()
          print "match.team2_score%(set)d = 0" % locals()
          set += 1
        for i in range(0, match["scores"][1]):
          print "match.team1_score%(set)d = 0" % locals()
          print "match.team2_score%(set)d = 1" % locals()
          set += 1
        print "match.save()"
        print "group.save()"
  else:
    for (name, league) in leagues:
      print ""
      print name
      for row in league:
        print " ".join(row)


"""
from django.contrib.auth.models import User
import wsrc.site.usermodel.models as user_models


for p in players: 
  details = p[1]
  if details is None:
    print "Not in booking system: " + p[0] 
  list = user_models.Player.objects.filter(user__first_name=details["first_name"], user__last_name=details["last_name"])
  if not list:
    if False:
      print "Not in database: " + p[0]
      print "Possible matches: " + str(user_models.Player.objects.filter(user__last_name=details["last_name"]))
    else:
      username = p[0].replace(" ", "_").lower()
      if username == "matt_oconnor":
        continue
      print "inserting: " + username + " - " + str(details)
      u = User(username=username, first_name=details["first_name"], last_name=details["last_name"], email=details["email"])
      u.save()
      u.player.cell_phone=details["mobile"]
      u.player.other_phone=details["phone"]
      u.player.save()

"""
