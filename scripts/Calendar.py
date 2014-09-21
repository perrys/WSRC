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

SERVICE_ACCOUNT_NAME='684425597639-rmr9jk9hrrbtt4uqs0v36cgfq5ksb77s@developer.gserviceaccount.com'
CALENDAR_RW_SCOPE="https://www.googleapis.com/auth/calendar"
MIDNIGHT = datetime.time(0, 0)
UK_TIMEZONE = "Europe/London"
UK_TZINFO = GBEireTimeZone()
UTC_TZINFO = UTC()
LOGGER = logging.getLogger(__name__)

def _getService():
  http = httplib2.Http()
  storage = oauth2client.file.Storage(os.path.expanduser('~/etc/.credentials'))
  credentials = storage.get()
  if credentials is None or credentials.invalid == True:
    fh = open(os.path.expanduser("~/etc/WSRC_Calendar-0d05fd27ef4c.p12"))
    key = fh.read()
    fh.close()
    credentials = oauth2client.client.SignedJwtAssertionCredentials(service_account_name=SERVICE_ACCOUNT_NAME, private_key=key, scope=CALENDAR_RW_SCOPE)
  http = credentials.authorize(http)
  return apiclient.discovery.build('calendar', 'v3', http=http)

class CalendarWrapper:

  def __init__(self, calendarId, service=_getService()):
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
      self.service.events().update(calendarId=self.calendarId, body=evt.googleEvent).execute()
    
class Event:

  def __init__(self, name, link, time=None, duration=None, location=None, id=None, googleEvent=None):
    self.name = name
    self.link = link
    self.time = time
    self.duration = duration
    self.location = location
    self.id = (id is None) and uuid.uuid1().hex or id
    self.googleEvent = googleEvent

  def toGoogleCalendarEvent(self):
    return {
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
      # 'attendees': [
      #   {
      #     'email': 'foo@bar.com',
      #     # Other attendee's data...
      #     },
      #   ],
      'source': {
        'title': 'WSRC Booking System',
        'url': self.link
        }
      }

  @staticmethod
  def fromGoogleCalendarEvent(evt):
    def fromISODateTime(s):
      if not s.endswith("Z"):
        raise Exception("Expected UTC time, unsure how to interpret")
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

  def mergeIntoGoogleEvent(self, evt):
    gevt = evt.googleEvent
    gevt['summary'] = self.name
    gevt['location'] = self.location,
    gevt['start']['dateTime'] = self.time.isoformat(),
    gevt['end']['dateTime'] = (self.time + self.duration).isoformat(),
    gevt['source']['url'] = self.link

  def identicalTo(self, other):
    mine,theirs = [(x.name, x.time, x.duration, x.link, x.location) for x in self, other]
    return mine == theirs

  def __key(self):
      return (self.time, self.location)

  def __eq__(x, y):
      return x.__key() == y.__key()

  def __hash__(self):
      return hash(self.__key())
