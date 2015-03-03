# This file is part of WSRC.
#
# WSRC is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# WSRC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with WSRC.  If not, see <http://www.gnu.org/licenses/>.

import cookielib
import datetime
import logging
import httplib
import sys
import urllib
import urllib2

import wsrc.utils.timezones as time_utils
import scrape_page

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

class MyHTTPRedirectHandler(urllib2.HTTPRedirectHandler):
    def __init__(self):
      self.redirections = []
    def redirect_request(self, req, fp, code, msg, headers, newurl):
      self.redirections.append([code, msg, headers, newurl])
      return urllib2.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, headers, newurl)
    def clear(self):
      self.redirections = []

class SimpleHttpClient:
  "Simple httpclient which keeps session cookies and does not follow redirect requests"
  def __init__(self, base_url):
    self.base_url = base_url
    self.cookiejar = cookielib.CookieJar()
    self.redirect_recorder = MyHTTPRedirectHandler()
    self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookiejar), self.redirect_recorder)

  def request(self, selector, params=None, timeout=None):
    """Make a request for the given selector. This method returns a file like object as specified by urllib2.urlopen()"""
    url = self.base_url + selector
    if params is not None:
      params = urllib.urlencode(params)
    LOGGER.debug("opening url %(url)s, params: %(params)s" % locals())
    self.redirect_recorder.clear()
    fh = self.opener.open(url, params, timeout)
    return fh

  def get(self, selector, params=None, timeout=None):
    """Make a GET request for the given selector. This method returns a file like object as specified by urllib2.urlopen()"""
    if params is not None:
      params = urllib.urlencode(params)
      selector = "%s?%s" % (selector, params)
    return self.request(selector, None, timeout)

class BookingSystemSession:

  BASE_URL            = "http://www.court-booking.co.uk"
  LOGIN_PAGE          = "/WokingSquashClub/admin.php"
  BOOKING_PAGE        = "/WokingSquashClub/edit_entry_handler_fixed.php"
  DELETE_BOOKING_PAGE = "/WokingSquashClub/del_entry.php"
  WEEK_VIEW_PAGE      = '/WokingSquashClub/week.php'

  def __init__(self, username=None, password=None):
    self.client = SimpleHttpClient(BookingSystemSession.BASE_URL)

    if username is None: # don't attempt to log in if no username supplied.
      return

    self.username = username
    params = {
      "NewUserName" : username, 
      "NewUserPassword" : password,
      "TargetURL" : "admin.php?",
      "Action" : "SetName"
      }
    response = self.client.request(BookingSystemSession.LOGIN_PAGE, params)
    body = response.read()

    if "You are %(username)s" % self.__dict__ not in body:
      status = response.getcode()
      raise Exception("Login failed - username not reported, status: %(status)d, body: %(body)s" % locals())

    LOGGER.info("logged in sucessfully." % locals())

  def delete_booking(self, id):
    id = int(id)
    params = {
      "id": id
      }
    response = self.client.get(BookingSystemSession.DELETE_BOOKING_PAGE, params)

    redirections = self.client.redirect_recorder.redirections
    if len(redirections) > 0 and redirections[0][0] == httplib.FOUND:
      LOGGER.info("deleted booking id %(id)d" % locals())
      return

    status = response.getcode()
    body = response.read()
    if body.find("The new booking will conflict") > -1:
      raise Exception("conflict! failed to book court %(court)d@%(timestring)s" % locals())
    raise Exception("unexpected status returned for booking request: %(status)d, response body: %(body)s" % locals())

  def make_booking(self, starttime, court, description=None, name=None):
    """Book a court. STARTTIME is a datetime.datetime object. COURT is
    a court number (1-3). DESCRIPTION, if supplied, is a string. NAME,
    if supplied, will be the shown as the booking name on the booking
    website."""

    if name is None:
      name = self.username

    def parse_datetime(datetime):
      return datetime.year, datetime.month, datetime.day, datetime.hour, datetime.minute

    (year, month, day, hour, minute) = parse_datetime(starttime)
    returnURL = "http://www.court-booking.co.uk/WokingSquashClub/day.php?year=%(year)s&month=%(month)s&day=%(day)s&area=1" % locals()
    params = {
      "year" : year,
      "month" : month,
      "day" : day,
      "hour" : hour,
      "minute" : minute,
      "duration" : "45",
      "dur_units" : "minutes",
      "room_id" : str(court),
      "type" : "I",
      "name" : name,
      "create_by" : self.username.lower(),
      "rep_id" : "0",
      "edit_type" : "series",
      "description" : description or "",
      "returl" : returnURL
      }

    timestring = time_utils.as_iso_datetime(starttime)

    response = self.client.get(BookingSystemSession.BOOKING_PAGE, params)
    redirections = self.client.redirect_recorder.redirections
    if len(redirections) > 0 and redirections[0][0] == httplib.FOUND:
      LOGGER.info("booked court %(court)d@%(timestring)s" % locals())
      return

    status = response.getcode()
    body = response.read()
    if body.find("The new booking will conflict") > -1:
      raise Exception("conflict! failed to book court %(court)d@%(timestring)s" % locals())
    raise Exception("unexpected status returned for booking request: %(status)d, response body: %(body)s" % locals())

  def get_week_view(self, year, month, day, court):
    "Retrieve the week view for a given court from the online booking system"
    params = {
      'year': str(year),
      'month': "%02d" % month,
      'day': "%02d" % day,
      'area': '1',
      'room': int(court)
      }
    response = self.client.get(BookingSystemSession.WEEK_VIEW_PAGE, params)
    status = response.getcode()
    body = response.read()
    if status != httplib.OK:
      raise Exception("failed to retrieve week view, status: %(status)d, body: %(body)s" % locals())
    return body
    
def get_week_view(year, month, day, court, session=None):
  if session is None:
    session = BookingSystemSession()
  return session.get_week_view(year, month, day, court)

def get_booked_courts(session=None):
  if session is None:
    session = BookingSystemSession()
  bookingSystemEvents = []
  date = time_utils.nearest_last_monday()
  # Loop over this week and next week:
  for td in (datetime.timedelta(14),): # (datetime.timedelta(0), datetime.timedelta(days=7)):
    date = date + td
    # Loop over courts 1..3
    for court in range(1,4):
      # Get data from the bookings system for this week and court:
      bookingSystemEventData = session.get_week_view(date.year, date.month, date.day, court)
      events = scrape_page.scrape_week_events(bookingSystemEventData, date, court)
      LOGGER.info("Found {0} court booking(s) for court {1} week starting {2}".format(len(bookingSystemEvents), court, date.isoformat()))
      bookingSystemEvents.extend([(event, court) for event in events])
  return bookingSystemEvents

def make_booking(self, username, password, starttime, court, description=None, name=None):
  session = BookingSystemSession(username, password)
  session.make_booking(starttime, court, description, name)

def delete_booking(self, username, password, event_id):
  session = BookingSystemSession(username, password)
  session.delete_booking(event_id)



def test_create_and_delete_booking():
  # quick test

  session = BookingSystemSession(sys.argv[1], sys.argv[2])
  for cookie in session.client.cookiejar:
    print cookie

  if len(sys.argv) > 3:
    event_id = int(sys.argv[3])
    session.delete_booking(event_id)
  else:
    # book a court 1 year from today
    today = datetime.date.today()
    court_time = datetime.datetime(today.year+1, today.month, today.day, 19, 0, 0) # may fail on a leap day ??
    session.make_booking(court_time, 1, description="*** Test booking description. ***", name="** TEST NAME **")

def test_get_booked_courts():

  bookings = get_booked_courts()
  for (evt, court) in bookings:
    print evt.name, evt.time, court, evt.get_booking_id(), evt.description

if __name__ == "__main__":

  logging.basicConfig(format='%(asctime)-10s [%(levelname)s] %(message)s',datefmt="%Y-%m-%d %H:%M:%S")

  test_process_events()
  
