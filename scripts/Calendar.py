#!/usr/bin/python

import datetime
import httplib2
import logging
import os.path
import sys
import uuid

from GBEireTimeZone import GBEireTimeZone
from GBEireTimeZone import UTC

# installation:
# pip install --upgrade google-api-python-client
# (not needed?) sudo apt-get install python-gflags

import apiclient.discovery
import oauth2client.client
import oauth2client.file

oauth2client.client.logger.setLevel(logging.DEBUG)

# Credentials previously obtained from the google developers console...
SERVICE_ACCOUNT_NAME='684425597639-rmr9jk9hrrbtt4uqs0v36cgfq5ksb77s@developer.gserviceaccount.com'
PRIVATE_KEY_FILE=os.path.expanduser("~/etc/WSRC_Calendar-0d05fd27ef4c.p12")
CREDENTIALS_CACHE_FILE=os.path.expanduser('~/etc/.credentials')
CALENDAR_RW_SCOPE="https://www.googleapis.com/auth/calendar"

UK_TIMEZONE = "Europe/London"
UK_TZINFO = GBEireTimeZone()
UTC_TZINFO = UTC()
LOGGER = logging.getLogger(__name__)

def _getService():
  """Get and authenticated Google API service wrapper based on previously registered and stored credentials"""
  http = httplib2.Http()
  storage = oauth2client.file.Storage(CREDENTIALS_CACHE_FILE)
  credentials = storage.get()
  if credentials is None or credentials.invalid == True:
    fh = open(PRIVATE_KEY_FILE)
    key = fh.read()
    fh.close()
    credentials = oauth2client.client.SignedJwtAssertionCredentials(service_account_name=SERVICE_ACCOUNT_NAME, private_key=key, scope=CALENDAR_RW_SCOPE)
  http = credentials.authorize(http)
  return apiclient.discovery.build('calendar', 'v3', http=http)

class CalendarWrapper:
  """Simple wrapper for a given calendar service"""

  def __init__(self, calendarId, service=_getService()):
    """Create a new wrapper instance with the given calendar Id"""
    self.service = service
    self.calendarId = calendarId
    self.testing = False

  def addEvent(self, evt, colorId=None):
    LOGGER.info("Adding new event: {evt.name} [{evt.location}@{evt.time:%Y-%m-%d %H:%M:%S}]".format(**locals()))
    if not self.testing:
      gevt = evt.toGoogleCalendarEvent()
      if colorId is not None:
        gevt["colorId"] = colorId
      self.service.events().insert(calendarId=self.calendarId, body=gevt).execute()

  def listEvents(self, cutoff):
    cutoff = datetime.datetime.combine(cutoff, datetime.time(0,0)).isoformat() + "Z"
    page_token = None
    eventList = []
    while not self.testing:
      events = self.service.events().list(calendarId=self.calendarId, timeMin=cutoff, pageToken=page_token).execute()
      eventList.extend(events['items'])
      page_token = events.get('nextPageToken')
      if not page_token:
        break
    return [Event.fromGoogleCalendarEvent(evt) for evt in eventList]

  def deleteEvent(self, evt):
    LOGGER.info("Deleting event {evt.name} [{evt.location}@{evt.time:%Y-%m-%d %H:%M:%S}]".format(**locals()))
    if not self.testing:
      self.service.events().delete(calendarId=self.calendarId, eventId=evt.id).execute()

  def updateEvent(self, evt):
    LOGGER.info("Updating event {evt.name} [{evt.location}@{evt.time:%Y-%m-%d %H:%M:%S}]".format(**locals()))
    if not self.testing:
      self.service.events().update(calendarId=self.calendarId, eventId=evt.id, body=evt.toGoogleCalendarEvent()).execute()
    
class Event:
  "Simple wrapper for a calendar event. Has some utilities to convert to/from Google calendar event structures."

  def __init__(self, name, link, time=None, duration=None, location=None, id=None, googleEvent=None):
    self.name = name
    self.link = link
    self.time = time
    self.duration = duration
    self.location = location
    self.id = (id is None) and uuid.uuid1().hex or id
    self.googleEvent = googleEvent

  def toGoogleCalendarEvent(self):
    gevt = self.googleEvent
    if gevt is None:
      self.googleEvent = gevt = {}
    gevt.update({
      'summary': self.name,
      'location': self.location,
      'id': self.id,
      'start': {
        'dateTime': self.time.isoformat(),
        'timeZone': UK_TIMEZONE
        },
      'end': {
        'dateTime': (self.time + self.duration).isoformat(),
        'timeZone': UK_TIMEZONE
        },
      'source': {
        'title': 'WSRC Booking System',
        'url': self.link
        }
      })
    return gevt

  @staticmethod
  def fromGoogleCalendarEvent(evt):
    def fromISODateTime(s):
      if not s.endswith("Z"):
        raise Exception("Expected UTC time, unsure how to interpret: " + s)
      s = s[:-1]
      dt = datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
      dt = dt.replace(tzinfo=UTC_TZINFO)
      dt = dt.astimezone(UK_TZINFO)
      return dt
    start, end = [fromISODateTime(s) for s in evt["start"]["dateTime"], evt["end"]["dateTime"]]
    link = evt.get("source")
    if link is not None:
      link = link["url"]
    return Event(
      name=evt["summary"],
      link=link,
      time=start,
      duration=end-start,
      location=evt["location"],
      id=evt["id"],
      googleEvent=evt)

  def mergeFrom(self, evt):
    "Copy the details of the given event into this event"
    # update all fields except Id - if this started as a google
    # calendar event don't want to overwrite the id with a random one.
    self.name = evt.name
    self.link = evt.link
    self.time = evt.time
    self.duration = evt.duration
    self.location = evt.location

  def identicalTo(self, other):
    mine,theirs = [(x.name, x.time, x.duration, x.link, x.location) for x in self, other]
    return mine == theirs

  def __key(self):
      return (self.time, self.location) # considered the same if start time and location are the same

  def __eq__(x, y):
      return x.__key() == y.__key()

  def __hash__(self):
      return hash(self.__key())
