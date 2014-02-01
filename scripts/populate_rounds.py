#!/usr/bin/python

import sys
import datetime

def previousSunday(date):
  date -= datetime.timedelta(days=7)
  while (date.weekday() != 6):
    date += datetime.timedelta(days=1)
  return date
  

if __name__ == "__main__":
  id = int(sys.argv[1])
  date = datetime.datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
  nrounds = int(sys.argv[3])
  for i in range(nrounds, 0, -1):
    dateStr = date.isoformat()
    print "insert into TournamentRound values (%(id)d, %(i)d, \"%(dateStr)s\");" % locals()
    date = previousSunday(date)
