#!/usr/bin/python

import datetime
import sys
import os.path
from bs4 import BeautifulSoup
from Calendar import Event
from GBEireTimeZone import GBEireTimeZone

UK_TZINFO = GBEireTimeZone()

def tagGenerator(first, func=lambda(x): x.next_sibling, filt=lambda(x): hasattr(x, "name")):
  while first is not None:
    if filt(first):
      yield first
    first = func(first)

def convertNBSP(s):
  return s.replace(u'\xa0', ' ')

def cellContent(c):
  return convertNBSP(c.string)

def parseBooking(cell):
  link = cell.a
  if link is None:
    return cellContent(cell)
  return Event(cellContent(link), 'http://www.court-booking.co.uk/WokingSquashClub/' + link['href'])

def parseWeekRow(row):

  class Result:
    def __init__(self, time, bookings):
      time = datetime.datetime.strptime(time, '%H:%M')
      self.time = datetime.time(time.hour, time.minute, tzinfo=UK_TZINFO)
      self.bookings = bookings

  slots = []
  first = row.td

  def filtfunc(cell):
    if hasattr(cell, "name") and cell.name == 'td':
      cssclasses = cell.get("class") or []
      return "red" not in cssclasses
    return False

  result = Result(first.a.text, []) 

  for cell in tagGenerator(first, filt=filtfunc):
    cssclasses = cell.get("class")
    if cssclasses is not None and ('I' in cssclasses or 'E' in cssclasses):
      booking = parseBooking(cell)
      if booking is not None:
        result.bookings.append(booking)
        continue
    result.bookings.append(None)
  if len(result.bookings) != 7:
    raise Exception("Error parsing week row, expected 7 days, got {n}".format(n=len(result.bookings)))

  return result
                       
def processWeekPage(soup) :
  first_col_cell = soup.find('td', class_='red')
  if first_col_cell is None:
    raise Exception('Unable to parse - could not find first column in table')
  slots = []
  first_data_row = first_col_cell.parent
  title_row = first_data_row.previous_sibling
  for row in tagGenerator(first_data_row):
    data = parseWeekRow(row)
    slots.append(data)
  return slots

def extractEvents(time_list, first_date, location):

  quarterHour = datetime.timedelta(minutes=15)

  result = []
  for i in range(0,7):
    day_bookings = []
    result.append(day_bookings)
    today = first_date + datetime.timedelta(days=i)
    for j,row in enumerate(time_list):
      booking = row.bookings[i]
      if booking is not None:
        if isinstance(booking, Event):
          booking.time = datetime.datetime.combine(today, row.time)
          booking.duration = quarterHour
          booking.location = location
          day_bookings.append(booking)
        elif isinstance(booking, unicode) and booking.strip() == '"':
          if len(day_bookings) == 0:
            raise Exception("encountered ditto before a booking at time {time} for day {i}".format(time=str(row.time), i=i))
          booking = day_bookings[-1] 
          booking.duration = booking.duration + quarterHour
        else:
          raise Exception("unable to parse cell at time {time} for day {i}, text=\"{text}\"".format(time=str(row.time), i=i, text=booking))

  def flatten(l):
    return [item for sublist in l for item in sublist]

  return flatten(result)

def scrapeWeekEvents(eventData, first_date, location):
  soup = BeautifulSoup(eventData, "lxml")
  time_list = processWeekPage(soup)
  return extractEvents(time_list, first_date, location)

if __name__ == "__main__":
  infile = sys.stdin
  if len(sys.argv) > 1:
    infile = open(os.path.expanduser(sys.argv[1]))
  entries = scrapeWeekEvents(infile, datetime.date(2014,9,22), "WSRC Court 1")
  for e in entries:
      print e.__dict__
  
