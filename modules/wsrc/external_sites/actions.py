#!/usr/bin/python

import datetime
import re
import os
import logging
import sys

sys.path.append("/home/stu/dev/WSRC/modules")

import wsrc.utils.email_utils
import wsrc.utils.text
import wsrc.external_sites.evt_filters as evt_filters

class Notifier:
  def __init__(self, config, smtp_config):
    self.email = config.email
    self.smtp_config = smtp_config
    self.firstname = config.firstname
    self.testEvent = config.filter
    self.templateEnv = Environment(loader=PackageLoader("wsrc", "jinja2_templates"))
    self.events = []

  @staticmethod
  def configs_from_DB(current_time=None):
    from wsrc.site.usermodel.models import Player
    from wsrc.site.models import EventFilter
    userfilters = dict()
    def get_or_create(id):
      ulist = userfilters.get(id)
      if ulist is None:
        userfilters[id] = ulist = []
      return ulist
    filters = EventFilter.objects.filter(player__user__is_active=True)
    # populate map with lists of event filters keyed by player id
    for filter in filters:
      timefilt = evt_filters.TimeOfDay(filter.earliest, filter.latest)
      days = [o.day for o in filter.days.all()]
      dayfilt = evt_filters.DaysOfWeek(days)
      futurefilt = evt_filters.IsFutureEvent(delay=datetime.timedelta(minutes=filter.notice_period_minutes))
      combined_filter = evt_filters.And([timefilt, dayfilt, futurefilt])
      get_or_create(filter.player.id).append(combined_filter)
    # for each id, convert event filter list into combined filter:
    for id, filters in userfilters.iteritems():
      player = Player.objects.get(pk=id)
      not_userfilt = evt_filters.Not(evt_filters.IsPerson(player.get_full_name()))
      playerfilt = evt_filters.And([not_userfilt, evt_filters.Or(filters)])
      userfilters[id] = playerfilt
    return userfilters

  def __call__(self, evt):
    if self.testEvent(evt):
      self.events.append(evt)

  def process_all_events(self):

    if len(self.events) == 0:
      return

    rows = []
    rows.append(["Date", "Time", "Court", "Booking Link"])
    court_re = re.compile("Court ([1-3]),")
    for evt in sorted(self.events, key=lambda x: x.time):
      match = court_re.search(evt.location)
      link = court = ""
      if match is not None:
        court = match.group(1)
        link = "http://www.court-booking.co.uk/WokingSquashClub/edit_entry_fixed.php?room={court}&area=1".format(**locals())
        link += "&hour={d.hour}&minute={d.minute}&year={d.year}&month={d.month}&day={d.day}".format(d=evt.time)
      else:
        LOGGER.error("unable to get court number from location: " + evt.location)
      rows.append([evt.time.strftime("%a %d %b"), evt.time.strftime("%H:%M"), court, link])
    tbl = dict()
    tbl["rawdata"] = rows
    tbl["hasHeader"] = True
    tbl["textData"] = wsrc.utils.text.formatTable(tbl["rawdata"], tbl["hasHeader"], nspaces=1)
    subject = "Court Cancellations"
    kwargs = {
      "plural": wsrc.utils.text.plural, 
      "match": re.match, 
      "subject": subject,
      "firstname": self.firstname,
      "tables": {"cancellations": tbl}
      }

    def render(isHTML):
      kwargs["isHTML"] = isHTML
      template = self.templateEnv.get_template("cancellation.html")
      return template.render(**kwargs)

    sender = "stewart.c.perry@gmail.com"
    wsrc.utils.email.send_mixed_mail(sender, self.email, subject, render(False), render(True), self.smtp_config)

if __name__ == "__main__":
  os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wsrc.site.settings.settings")
  logging.basicConfig(format='%(asctime)-10s [%(levelname)s] %(message)s',datefmt="%Y-%m-%d %H:%M:%S")

  import django
  if hasattr(django, "setup"):
    django.setup()

  import pprint
  from wsrc.utils.timezones import UK_TZINFO
  configs = Notifier.configs_from_DB()
  myconfig = configs[1017]
  from wsrc.external_sites.cal_events import Event
  evt = Event("Stewart Perry", None, datetime.datetime(2015, 8, 3, 19, 0, tzinfo=UK_TZINFO), datetime.timedelta(minutes=15))
  assert(not myconfig(evt))
  evt.name = "Foo Bar"
  assert(myconfig(evt))
