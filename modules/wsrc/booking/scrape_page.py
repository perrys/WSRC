#!/usr/bin/python

import datetime
import logging
import sys
import os.path
from bs4 import BeautifulSoup
from cal_events import Event
from wsrc.utils.timezones import GBEireTimeZone

UK_TZINFO = GBEireTimeZone()
LOGGER = logging.getLogger(__name__)

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

def get_tag_content(c):
  def cvt_nbsp(s):
    return s.replace(u'\xa0', ' ')
  return cvt_nbsp(c.string)

def process_booking(cell):
  """Parse the cell contents into a either a string (in the case of
  text-only content, such as dittos), or a partially constructed Event
  object. The Event contains just the description (i.e. member name)
  and link. The time fields are added later as part of row/page
  processing"""
  link = cell.a
  if link is None:
    return get_tag_content(cell)
  return Event(get_tag_content(link), 'http://www.court-booking.co.uk/WokingSquashClub/' + link['href'])

def process_week_row(row):
  """Parse a 15-minute row in the weekly timetable, returning a time
  string and a list of 7 Event objects, or None if the cell is empty"""
  class Result:
    def __init__(self, time, bookings):
      time = datetime.datetime.strptime(time, '%H:%M')
      self.time = datetime.time(time.hour, time.minute, tzinfo=UK_TZINFO)
      self.bookings = bookings

  slots = []
  first = row.td
  result = Result(first.a.text, []) 

  # filter function for the row generator, excludes the first and lass
  # columns which have css class "red"
  def filtfunc(cell):
    if hasattr(cell, "name") and cell.name == 'td':
      cssclasses = cell.get("class") or []
      return "red" not in cssclasses
    return False

  # loop over valid cells in the row
  for cell in tag_generator(first, filt=filtfunc):
    cssclasses = cell.get("class") # interesting cells are identifiable by their CSS class:
    if cssclasses is not None and ('I' in cssclasses or 'E' in cssclasses):
      booking = process_booking(cell)
      if booking is not None:
        result.bookings.append(booking)
        continue
    result.bookings.append(None) # by default add None for this day

  if len(result.bookings) != 7:
    raise Exception("Error parsing week row, expected 7 days, got {n}".format(n=len(result.bookings)))

  return result
                       
def process_week_page(soup) :
  """Parse the weekly timetable for a court, returning a list of
  objects representing the 15-minute slots, in time order. Each object
  contains the fields "time" and "bookings", which are respectively
  the time (as a string) and a list of 7 objects representing the cell
  content, either an Event object, a string, or None."""
  first_col_cell = soup.find('td', class_='red')
  if first_col_cell is None:
    html = soup.prettify("utf-8")
    Logger.error("parse error, soup=\n" + html);
    raise Exception('Unable to parse - could not find first column in table')
  slots = []
  first_data_row = first_col_cell.parent
  title_row = first_data_row.previous_sibling
  def filtfunc(cell):
    return hasattr(cell, "name") and cell.name == 'tr'
  for row in tag_generator(first_data_row, filt=filtfunc):
    data = process_week_row(row)
    slots.append(data)
  return slots

def extract_events(time_list, first_date, location):
  """Process all of the information scraped from the page to produce a list of Event objects.
  TIME_LIST is the list of 15-minute slots representing the court bookings for a week at that time.
  FIRST_DATE is the date of the first column (which should be a Monday)
  LOCATION is a description of the court"""
  quarterHour = datetime.timedelta(minutes=15)

  result = []
  for i in range(0,7):
    day_bookings = []
    result.append(day_bookings)
    today = first_date + datetime.timedelta(days=i) # Week begins on Monday
    for j,row in enumerate(time_list):
      booking = row.bookings[i]
      if booking is not None:
        if isinstance(booking, Event):
          booking.time = datetime.datetime.combine(today, row.time)
          booking.duration = quarterHour
          booking.location = location
          day_bookings.append(booking)
        elif isinstance(booking, unicode) and booking.strip() == '"': # Process dittos
          if len(day_bookings) == 0:
            raise Exception("encountered ditto before a booking at time {time} for day {i}".format(time=str(row.time), i=i))
          booking = day_bookings[-1] 
          booking.duration = booking.duration + quarterHour
        else:
          raise Exception("unable to parse cell at time {time} for day {i}, text=\"{text}\"".format(time=str(row.time), i=i, text=booking))

  def flatten(l):
    return [item for sublist in l for item in sublist]

  return flatten(result)

def scrape_week_events(eventData, first_date, location):
  soup = BeautifulSoup(eventData, "lxml")
  time_list = process_week_page(soup)
  return extract_events(time_list, first_date, location)

if __name__ == "__main__":
  infile = sys.stdin
  if len(sys.argv) > 1:
    infile = open(os.path.expanduser(sys.argv[1]))
  entries = scrape_week_events(infile, datetime.date(2014,9,22), "WSRC Court 1")
  for e in entries:
      print e.__dict__
  
