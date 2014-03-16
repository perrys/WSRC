#!/usr/bin/python

import MySQLdb
import sys
import os.path

def batchCursor(store, batchsize=512):
  while True:
    results = store.fetchmany(batchsize)
    if not results:
      break;
    for result in results:
      yield result

class DataBase:

  def __init__(self):
    self.dbh = MySQLdb.connect(user="root", db="squash", passwd="squash")

  def queryAndStore(self, sql, params=None, wantFields = False):
    c = self.dbh.cursor()
    c.execute(sql, params)
    results = [row for row in batchCursor(c)]
    if wantFields:
      field_names = [i[0] for i in c.description]
      return results, field_names
    return results

  def update(self, sql, params=None):
    c = self.dbh.cursor()
#    print sql, params
    c.execute(sql, params)
    self.dbh.commit()

def roundComparer(lhs, rhs):
  result = len(lhs) - len(rhs)
  if result == 0:
    result = cmp(lhs, rhs)
  return result

def getOrAdd(d, k):
  l = d.get(k)
  if l is None:
    l = []
    d[k] = l
  return l

def addMatchNumbers(t_id):
  dbh = DataBase()
  params = [t_id]
  result = dbh.queryAndStore("select Id, Round, MatchNumber from TournamentMatch where Tournament_Id = %s", params)
  rounds = dict()
  for row in result:
    l = getOrAdd(rounds, row[1])
    l.append(row)
  for roundMatches in rounds.itervalues():
    roundMatches.sort(roundComparer, lambda(x): x[0])
    for i,row in enumerate(roundMatches):
      params = [i, t_id, row[0]]
      dbh.update("update TournamentMatch set MatchNumber = %s where Tournament_Id = %s and Id = %s", params)

def updateUsers(users):
  dbh = DataBase()
  for user in users:
    result = dbh.queryAndStore("select Id from User where Name = %s", [user])
    if len(result) == 0:
      dbh.update("insert into User set Name = %s", [user])
      print user

def getEmail(users):
  dbh = DataBase()
  for user in users:
    result = dbh.queryAndStore("select Email from User where Name = %s", [user])
    if len(result) == 0:
      result = dbh.queryAndStore("select Email from BookingSystemContact where Name = %s", [user])
      if len(result) == 0:
        sys.stderr.write("Missing user: %(user)s\n" % locals())
        continue
      print result[0][0]
    else:
      print result[0][0]
  
def updateSeeds(tournamentId, filename):
  fh = open(os.path.expanduser(filename))
  dbh = DataBase()
  for line in fh:
    tokens = line.split("\t")
    params = [tournamentId, tokens[0], tokens[8], tokens[9]]
    print tokens
    dbh.update("insert into Seed values (%s, (select Id from User where Name = %s), %s, %s)", params) 
            

if __name__ == "__main__":
#  for i in range(1,9):
#    addMatchNumbers(i)
#  updateUsers(["Adrian Hayward", "Andrew Grace", "Andy Todd", "Anthony Muggeridge", "Brian Greatorex", "Chris Bartlett", "Craig Swinerd", "Danny Jones", "Dave Wallond", "David Alford", "David Dommett", "David Guy", "David Ironside", "Dennis White", "Diane Benford", "Ed Walters", "Elliot Lee", "Eric Butterworth", "Freddie Lawson", "Gerry Summers", "Graham Norton", "Hamza Ali", "Iain Bremner", "Ian Dermody", "Jack Ross", "Janik Karunaratne", "John Bryant", "John Hughes", "Karl Loynton", "Keith Brakefield", "Keith Holdaway", "Kerryn Bartlett", "Kieron Harwood", "Leigh Masters", "Leroy Valentine", "Martin Shelley", "Mike Herington", "Mike McElhatton", "Mike Rivers", "Mike Wardle", "Nicholas Hiley", "Paddy Bascombe", "Paul Garbutt", "Paul Perry", "Peter Richardson", "Ragoo Pema", "Ralph Goldstein", "Rich Jamieson", "Rob Heasman", "Robin Griffiths", "Rob Kemp", "Rob Ready", "Ryan McLaughlin", "Sharon Bains", "Simon Browne", "Spencer Harris", "Stewart Perry", "Sukhy Bains", "Toby Fenton", "Tom Pewter", "Usman Hussain"])
#  updateSeeds(sys.argv[1], sys.argv[2])
#  getEmail(["Paul Reilly", "Michael Wardle", "Paul Garbutt", "Peter Richardson", "Dave Wallond", "Adrian Hayward", "Rob Heasman", "Jack Ross", "Stuart Bicknell", "John Hughes", "Chris Burton", "Herman Van Den Berg", "Noel Laycock", "Rob Kemp", "Spencer Harris", "Ian Salmond", "Chris Bartlett", "Kieron Harwood", "Freddie Lawson", "Mike McElhatton", "Graham Norton", "Usman Hussain", "David Lyscom", "Patrick Bascombe", "Ivor Simpson", "Paul Perry", "Elliot Lee", "Keith Holdaway", "David Greatorex", "Martin Shelley", "Andy Bartlett", "Jez Foulsham", "Danny Jones", "Shahid Azeem", "John Bryant", "Leroy Valentine", "Mike Neale", "Peter Key", "Sarah Verdin", "Kerryn Bartlett", "Simon Browne", "David Webb", "Eric Butterworth", "Toby Fenton", "Ian Dermody", "David Dommett", "Mike Thacker", "Tito Nath", "Brian Greatorex", "David Guy", "Mike Calvert", "Phil Peakin", "Nicky Hayden", "Rob Ready", "Louise Bacon", "Annie Lane", "Diane Benford"])
  updateUsers(["Andrea Mercer", "Alex Mercer", "Mark Tuddenham", "Ben Payne", "Oliver Eager", "Tvishi Agarwal", "Linus Fuge", "Alex McLean", "Toby Harris", "Amy Price", "Tiffany Kuk", "Dominic Kuk", "Benjamin Kuk", "Stephan Grace", "Philip Grace", "Nick Hiley", "James Bremner", "Hamza Ali", "Muneer Ali", "George Gervasio", "Jack Evans", "Sachi Raju", "Hugh Boorman", "Rajin Mangat"])
