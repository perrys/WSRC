#!/usr/bin/python

import datetime
import logging
import sys
import os.path
import re

from bs4 import BeautifulSoup
from wsrc.utils.timezones import GBEireTimeZone
import wsrc.utils.url_utils as url_utils

UK_TZINFO = GBEireTimeZone()
LOGGER = logging.getLogger(__name__)

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

class CellContent:
  def __init__(self, tag):
    self.text = cvt_nbsp(tag.get_text(strip=True)).strip()
    self.link = None
    link = tag.find('a')
    if link is not None:
      self.link = link['href']
  def __str__(self):
    return self.text
      
def cvt_nbsp(s):
  return s.replace(u'\xa0', ' ')

def get_tag_content(c):
  return cvt_nbsp(c.string)

def count_backwards_tds(tag):
  return len([x for x in tag_generator(tag, next_func=lambda(x): x.previous_sibling, filt=CellPredicate('td'))])
  
def extract_id(link):
  if link is None:
    return None
  return url_utils.get_url_params(str(link)).get("id")

def process_booking(cell):
  """Parse the cell contents into a either a string (in the case of
  text-only content, such as dittos), or a partially constructed Event
  object. The Event contains just the description (i.e. member name)
  and link. The time fields are added later as part of row/page
  processing"""
  from wsrc.site.courts.models import BookingSystemEvent
  link = cell.a
  if link is None:
    return get_tag_content(cell)
  return BookingSystemEvent(name = get_tag_content(link), description=link.get("title"), event_id=extract_id(link.get("href")))

def process_week_row(row):
  """Parse a 15-minute row in the weekly timetable, returning a time
  string and a list of 7 BookingSystemEvent objects, or None if the cell is empty"""
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
  content, either an BookingSystemEvent object, a string, or None."""
  first_col_cell = soup.find('td', class_='red')
  if first_col_cell is None:
    html = soup.prettify("utf-8")
    LOGGER.error("parse error, soup=\n" + html);
    raise Exception('Unable to parse - could not find first column in table')
  slots = []
  first_data_row = first_col_cell.parent
  title_row = first_data_row.previous_sibling
  for row in tag_generator(first_data_row, filt=CellPredicate('tr')):
    data = process_week_row(row)
    slots.append(data)
  return slots

def extract_events(time_list, first_date, court_number):
  """Process all of the information scraped from the page to produce a list of Event objects.
  TIME_LIST is the list of 15-minute slots representing the court bookings for a week at that time.
  FIRST_DATE is the date of the first column (which should be a Monday)
  LOCATION is a description of the court"""

  from wsrc.site.courts.models import BookingSystemEvent
  quarterHour = datetime.timedelta(minutes=15)

  result = []
  for i in range(0,7):
    day_bookings = []
    result.append(day_bookings)
    today = first_date + datetime.timedelta(days=i) # Week begins on Monday
    for j,row in enumerate(time_list):
      booking = row.bookings[i]
      if booking is not None:
        if isinstance(booking, BookingSystemEvent):
          booking.start_time = datetime.datetime.combine(today, row.time)
          booking.end_time = booking.start_time + quarterHour
          booking.court = court_number
          day_bookings.append(booking)
        elif isinstance(booking, unicode) and booking.strip() == '"': # Process dittos
          if len(day_bookings) == 0:
            raise Exception("encountered ditto before a booking at time {time} for day {i}".format(time=str(row.time), i=i))
          booking = day_bookings[-1] 
          booking.end_time += quarterHour
        else:
          raise Exception("unable to parse cell at time {time} for day {i}, text=\"{text}\"".format(time=str(row.time), i=i, text=booking))

  def flatten(l):
    return [item for sublist in l for item in sublist]
  result = flatten(result)
  return result

def process_box_header(tag):
  """Parse a box from the old site's league table page"""
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
    for j in range(0,8):
      text = cvt_nbsp(col_iter.next().text).strip()
      data_cols.append(text)
  return (league_name, data_rows)

def scrape_week_events(eventData, first_date, court_number):
  soup = BeautifulSoup(eventData, "lxml")
  time_list = process_week_page(soup)
  events = extract_events(time_list, first_date, court_number)
  return events

def scrape_old_league_table(data):
  soup = BeautifulSoup(data, "lxml")
  headers = soup.find_all('td', text=re.compile("^Division:"))
  if len(headers) == 0:
    headers = soup.find_all('td', text=re.compile("^League\s+No"))
  return [process_box_header(h) for h in headers]
  

def scrape_table_generic(headerrow):
  headers = [cvt_nbsp(th.get_text()).strip() for th in headerrow.find_all("th")]
  rows = headerrow.find_next_siblings("tr")
  def process_row(row):
    row_id = row.get("data-id")    
    row_data = [CellContent(td) for td in row.find_all("td")]
    return (row_id, row_data)
  def filtfunc(cell):
    return hasattr(cell, "name") and cell.name == 'tr'
  result = [process_row(r) for r in tag_generator(headerrow.next_sibling, filt=filtfunc)]
  result = [r for r in result if len(r[1]) == len(headers)]
  def get_dict(row_id, row_data):
    result = dict(zip(headers, row_data))
    if row_id is not None:
      result['row_id'] = row_id
    return result
  return [get_dict(row_id, row_data) for row_id, row_data in result]

def scrape_fixtures_table(data):
  soup = BeautifulSoup(data, "lxml")
  toprowheader = soup.find('th', class_='boxtopmain')
  headerrow = toprowheader.parent
  return scrape_table_generic(headerrow)

def scrape_userlist(data):
  soup = BeautifulSoup(data, "lxml")
  toprowheader = soup.find_all('th')
  for th in toprowheader:
    if th.string == 'Rights':
      headerrow = th.parent
      break
  return scrape_table_generic(headerrow)


if __name__ == "__main__":
  import wsrc.external_sites

  infile = sys.stdin
  if len(sys.argv) > 1:
    infile = open(os.path.expanduser(sys.argv[1]))
  entries = scrape_week_events(infile, datetime.date(2014,9,22), 1)
  for e in entries:
      print e
  
