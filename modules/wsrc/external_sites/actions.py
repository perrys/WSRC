#!/usr/bin/python

from jinja2 import Environment, PackageLoader
import re

import wsrc.utils.email
import wsrc.utils.text

class Notifier:
  def __init__(self, config, smtp_config):
    self.email = config.email
    self.smtp_config = smtp_config
    self.firstname = config.firstname
    self.testEvent = config.filter
    self.templateEnv = Environment(loader=PackageLoader("wsrc", "jinja2_templates"))
    self.events = []

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
