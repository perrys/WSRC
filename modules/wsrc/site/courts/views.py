# -*- coding: utf-8 -*-
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

import datetime
import httplib
import httplib2
import json
import operator
import sys
import urllib

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, SuspiciousOperation, PermissionDenied
from django.core.mail import SafeMIMEMultipart, SafeMIMEText
from django.core.urlresolvers import reverse as reverse_url
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template import Template, Context, RequestContext
from django.template.response import TemplateResponse
from django.views.decorators.http import require_safe, require_http_methods

from icalendar import Calendar, Event, vCalAddress, vText

import wsrc.site.settings.settings as settings
from wsrc.site.models import BookingSystemEvent
from wsrc.site.usermodel.models import Player
from wsrc.utils.html_table import Table, Cell, SpanningCell
from wsrc.utils import timezones, email_utils

COURTS = [1, 2, 3]
START_TIME =  8*60 + 30
END_TIME   = 22*60 + 15
RESOLUTION = 15
EMPTY_DUR  = 3 * RESOLUTION
START_TIMES = [datetime.time(hour=t/60, minute=t%60) for t in range(START_TIME, END_TIME-RESOLUTION, RESOLUTION)]
DURATIONS = [datetime.timedelta(minutes=i) for i in range(15, END_TIME-START_TIME, 15)]

BOOKING_SYSTEM_EMAIL_ADRESS = "court_booking@wokingsquashclub.org"

class RemoteException(Exception):
  def __init__(self, body, status):
    msg = "Error {code} [{name}] - {body}".format(code=status, name=httplib.responses[status], body=body)
    super(RemoteException, self).__init__(msg)
    self.status = status
    self.body = body

class EmailingException(Exception):
  pass
    
def get_server_time(headers):
  for (key,val) in headers:
    if key.lower() == "date":
      if not (val.endswith("GMT") or val.endswith("UTC")):
        raise Exception("Expected server time to be returned in GMT")
      date = datetime.datetime.strptime(val, "%a, %d %b %Y %H:%M:%S %Z")
      return timezones.naive_utc_to_local(date, timezones.UK_TZINFO)

def query_booking_system(query_params={}, body=None, method="GET"):
  url = settings.BOOKING_SYSTEM_ORIGIN + settings.BOOKING_SYSTEM_PATH + "?" + urllib.urlencode(query_params)
  h = httplib2.Http()
  (resp_headers, content) = h.request(url, method=method, body=body)
  server_time = get_server_time(resp_headers.items())
  if resp_headers.status != httplib.OK:
      raise RemoteException(content, resp_headers.status)
  return server_time, json.loads(content)

def auth_query_booking_system(booking_user_id, data={}, query_params={}, method="POST"):
  booking_user_token = BookingSystemEvent.generate_hmac_token_raw("id:{booking_user_id}".format(**locals()))
  data = dict(data)
  data.update({
    "user_id": booking_user_id,
    "user_token": booking_user_token
  })
  return query_booking_system(query_params, json.dumps(data), method)

def get_bookings(date):
  today_str    = timezones.as_iso_date(date)
  tomorrow_str = timezones.as_iso_date(date + datetime.timedelta(days=1))
  params = {
    "start_date": today_str,
    "end_date": tomorrow_str,
    "with_tokens": 1
  }
  server_time, data = query_booking_system(params)
  courts = data[today_str]
  return server_time, dict([(int(i), v) for i,v in courts.iteritems()])

def get_booking(id):
  params = {
    "id": id,
    "with_tokens": 1
  }
  server_time, data = query_booking_system(params)
  result = None
  if data is not None and len(data) > 0:
    for date,courts in data.iteritems():
      for court, start_times in courts.iteritems():
        for start_time, slot in start_times.iteritems():
          slot["court"] = int(court)
          slot["date"] = date
          result = slot
  return server_time, result

def create_booking(booking_user_id, slot):
  start_time = slot["start_time"]
  data = {
    "date": timezones.as_iso_date(slot["date"]),
    "start_mins": start_time.hour * 60 + start_time.minute,
    "duration_mins": slot["duration"],
    "court": slot["court"],
    "name": slot["name"],
    "description": slot["description"],
    "type": slot["booking_type"],
    "token": slot["token"],
  }
  server_time, data = auth_query_booking_system(booking_user_id, data)
  return data

def create_booking_cell_content (slot, court, date):
  start_mins = slot["start_mins"]
  start = timezones.to_time(start_mins)
  end   = timezones.to_time(start_mins + slot["duration_mins"])
  result = "<div><div class='slot_time'>{start:%H:%M}&ndash;{end:%H:%M}<br><span class='court'>Court {court}</span></div></a>".format(**locals())
  if "id" in slot:
    result += "<a href='{path}/{id}' data-ajax='false'>{name}</a>".format(path=reverse_url('booking'), id=slot['id'], name=slot['name'])
  elif "token" in slot:
    params = {
      'start_time': slot['start_time'],
      'date': timezones.as_iso_date(date),
      'duration': slot['duration_mins'],
      'court': court,
      'token': slot['token']
    }
    slot.update({"court": court, "date": date})
    result += "<span class='available'><a href='{path}/?{params}' data-ajax='false'>(available)</a></span>".format(path=reverse_url('booking'), params=urllib.urlencode(params))
  result += "</div>"
  return result
    

def render_day_table(court_slots, date, server_time):
  start = START_TIME
  end   = END_TIME
  for (court, slots) in court_slots.iteritems():    
    for slot in slots.itervalues():
      t1 = slot["start_mins"]
      t2 = t1 + slot["duration_mins"]
      start = min(t1, start)
      end   = max(t2, end)
  nrows = (end - start) / RESOLUTION
  table = Table(len(COURTS)+1, nrows, {"class": "booking_day", "data-server-time": timezones.as_iso_datetime(server_time)})
  for i in range(0,nrows):
    table.addCell(Cell("", attrs={"class": "time-col"}, isHeader=True), 0, i)
  
      
  for court in COURTS:
    slots = court_slots[court]
    row_idx = 0
    slots = slots.values()
    slots.sort(key=operator.itemgetter("start_mins"))
    for slot in slots:
      if row_idx == 0:
        blank_rows = (slot["start_mins"] - start) / RESOLUTION
        row_idx += blank_rows
      duration_mins = slot["duration_mins"]      
      nrows =  duration_mins / RESOLUTION
      attrs = {"data-court": str(court)}
      classes = ["slot"]
      if "id" in slot:
        attrs['onclick'] = "document.location.href='{path}/{id}'".format(path=reverse_url('booking'), id=slot['id'])
        classes.append("booking")
        classes.append(slot["type"])
        for k in ["id", "type", "start_mins", "duration_mins", "created_by", "timestamp"]:
          attrs["data-" + k] = str(slot[k])
        descr = slot.get("description")
        if descr:
          attrs["title"] = descr
      elif "token" in slot:
        attrs["onclick"] = "wsrc.court_booking.instance.handle_booking_request(event, this)"
        classes.append("available")
        for k in ["token", "start_mins", "duration_mins"]:
          attrs["data-" + k] = str(slot[k])
      attrs["class"] = " ".join(classes)
      content = create_booking_cell_content(slot, court, date)
      cell = SpanningCell(1, nrows, content=content, attrs=attrs, isHTML=True)
      table.addCell(cell, court, row_idx)
      row_idx += nrows
      last_cell = cell
    last_cell.attrs["class"] += " column-last"
  last_cell.attrs["class"] += " last"

  table.compress()
  court_headers = "".join(["<th>Court {d}</th>".format(d=court) for court in COURTS])
  table_head = "<thead><tr><td class='time-col'></td>{courts}</tr></thead>".format(courts=court_headers)  
  return table.toHtmlString(table_head)


@require_safe
def day_view(request, date=None):
    if date is None:
        date = datetime.date.today()
    else:
        date = timezones.parse_iso_date_to_naive(date)
    server_time, bookings = get_bookings(date)
    table_html = render_day_table(bookings, date, server_time)
    if request.GET.get("table_only") is not None:
      return HttpResponse(table_html)
    context = {
      "date": date,
      "prev_date": date - datetime.timedelta(days=1),
      "next_date": date + datetime.timedelta(days=1),
      "day_table": table_html,
    }    
    return render(request, 'courts.html', context)

def validate_quarter_hour_duration(value):
  rem = value % 15
  if rem != 0:
    raise ValidationError("{value} is not a 15-minute multiple".format(**locals()))

def validate_quarter_hour(value):
  validate_quarter_hour_duration(value.minute)

def make_readonly_widget():
  return forms.TextInput(attrs={'class': 'readonly', 'readonly': 'readonly', 'style': 'text-align: left'})

def make_date_formats():
  return ['%a %d %b %Y', '%Y-%m-%d']

def make_datetime_formats():
  return [x + " %H:%M:%S" for x in make_date_formats()]
  
def format_date(val, fmts):
  v = datetime.datetime.strptime(val, fmts[1])
  return v.strftime(fmts[0])
  
class BookingForm(forms.Form):
  name = forms.CharField(max_length=80)
  description = forms.CharField(required=False, widget=forms.TextInput(attrs={'autofocus': '1'})
)

  date = forms.DateField(input_formats=make_date_formats())
  start_time = forms.TimeField(label="Time", input_formats=['%H:%M'], validators=[validate_quarter_hour],
                               widget=forms.Select(choices=[(t.strftime("%H:%M"), t.strftime("%H:%M")) for t in START_TIMES]))
  duration = forms.ChoiceField(choices=[(i.seconds/60, timezones.duration_str(i)) for i in DURATIONS])
  court = forms.ChoiceField(choices=[(i, str(i)) for i in COURTS])
  booking_type = forms.ChoiceField(choices=[("I", "Member"), ("E", "Club")])

  created_by = forms.CharField(max_length=80, label="Created By", widget=make_readonly_widget(), required=False)
  created_ts = forms.DateTimeField(label="Created At", input_formats=make_datetime_formats(), widget=make_readonly_widget(), required=False)
  timestamp  = forms.DateTimeField(label="Last Updated", input_formats=make_datetime_formats(), widget=make_readonly_widget(), required=False)
  
  booking_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
  created_by_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
  token = forms.CharField(max_length=32, required=False, widget=forms.HiddenInput())

  @staticmethod
  def transform_booking_system_entry(entry):
    mapping = {"booking_id": "id", "booking_type": "type", "duration": "duration_mins"}
    slot = dict(entry)
    for k, v in mapping.items():
      value = entry[v]
      slot[k] = value
      del slot[v]
    def format_date1(k, fmts):
      slot[k] = format_date(slot[k], fmts)
    format_date1("date", make_date_formats())
    format_date1("created_ts", make_datetime_formats())
    format_date1("timestamp", make_datetime_formats())
    return slot

def edit_entry_view(request, id=None):
  player = Player.get_player_for_user(request.user)
  booking_user_id = None if player is None else player.booking_system_id
  method = request.method
  if method == "POST" and  "method" in request.GET: # allow method override in query string of POST request, for html forms
    method = request.GET["method"]

  if method == "POST":
    if not request.user.is_authenticated():
      raise SuspiciousOperation()
#      return redirect('/login/?next=%s' % request.path)
    if booking_user_id is None:
      return HttpResponseForbidden("<p>Sorry, your login is not set up to book courts from this website.</p><p>Please contact <a href='mailto:webmaster@wokingsquashclub.org'>webmaster@wokingsquashclub.org</a> to get this fixed, and use the <a href='{server}'>old booking site</a> in the meantime.</p>".format(server=settings.BOOKING_SYSTEM_ORIGIN))    
    booking_form = BookingForm(request.POST)
    if booking_form.is_valid():
      try:
        new_booking = create_booking(booking_user_id, booking_form.cleaned_data)
        booking_data = dict(booking_form.cleaned_data)
        booking_data["booking_id"] = new_booking.get("id")
        send_calendar_invite(request, booking_data, [request.user], "create")
        return redirect(reverse_url(day_view) + "/" + timezones.as_iso_date(booking_form.cleaned_data["date"]))
      except RemoteException, e:
        booking_form.add_error(None, str(e))
      except EmailingException, e:
        booking_form.add_error(None, str(e))

  else:
    if id is None:
      initial_data = {
        'name': request.user.get_full_name(),
        'booking_type': 'I'
      }    
      for field in ['date', 'start_time', 'duration', 'court', 'token']:
        val = request.GET.get(field)
        if val is None:
          raise SuspiciousOperation("missing booking data")
        if field == 'date':
          val = format_date(val, make_date_formats())
        initial_data[field] = val
    else:
      initial_data = BookingForm.transform_booking_system_entry(get_booking(id))
    booking_form = BookingForm(data=initial_data)
    booking_form.is_valid()

  
  is_admin = False # TODO: keep these writable for admin
  readonly_fields = ['name', 'date', 'start_time', 'duration', 'court']
  hidden_fields = ['booking_type']
  
  days_diff = seconds_diff = None
  if id is None:
    mode = "create"
    hidden_fields.extend(['created_ts', 'created_by', 'timestamp'])
  else:
    mode = "view"
    if booking_form.is_valid():
      days_diff = server_time.date().toordinal() - booking_form.cleaned_data['date'].toordinal()
      seconds_diff = timezones.to_seconds(server_time.time()) - timezones.to_seconds(booking_form.cleaned_data['start_time'])
    if booking_user_id is not None and booking_form.is_valid() and booking_user_id == booking_form.cleaned_data.get("created_by_id"):
      mode = "update"
    elif is_admin:
      mode = "update"
      readonly_fields.remove("name")
      hidden_fields.remove("booking_type")
    else:
      readonly_fields.append("description")
  

  for field in readonly_fields:    
    widget = forms.TextInput(attrs={'class': 'readonly', 'readonly': 'readonly', 'style': 'text-align: left'})
    booking_form.fields[field].widget = widget
  for field in hidden_fields:
    booking_form.fields[field].widget = forms.HiddenInput()

  back = request.POST.get("next")
  if back is None:
    back = reverse_url(day_view)
    if booking_form.is_valid():
      back += "/" + timezones.as_iso_date(booking_form.cleaned_data["date"])

  context = {
    'booking_form': booking_form,
    'mode': mode,
    'back_url':  back,
    'days_diff': days_diff,
    'seconds_diff': seconds_diff
  }
  return render(request, 'booking.html', context)

def send_calendar_invite(request, slot, recipients, event_type):
  method = "CANCEL" if event_type == "delete" else "REQUEST"
  cal = create_icalendar(request, slot, recipients, method)
  encoding = settings.DEFAULT_CHARSET
  msg_cal = SafeMIMEText(cal.to_ical(), "calendar", encoding)
  msg_cal.set_param("method", method)
  context = {
    'event_type': event_type
  }
  context.update(slot)
  text_body, html_body = email_utils.get_email_bodies("BookingUpdate", context)
  msg_bodies = SafeMIMEMultipart(_subtype="alternative", encoding=encoding)
  msg_bodies.attach(SafeMIMEText(text_body, "plain", encoding))
  msg_bodies.attach(SafeMIMEText(html_body, "html", encoding))
  to_list = [user.email for user in recipients]
  subject="WSRC Court Booking - {date:%Y-%m-%d} {start_time:%H:%M} Court {court}".format(**slot)
  try:
    email_utils.send_email(subject, None, None,
                           from_address=BOOKING_SYSTEM_EMAIL_ADRESS,
                           to_list=to_list, cc_list=None,
                           extra_attachments=[msg_bodies, msg_cal])
  except Exception, e:
    err = ""
    if hasattr(e, "smtp_code"):
      err += "EMAIL SERVER ERROR [{smtp_code:d}] {smtp_error:s} ".format(**e.__dict__)
      if e.message:
        err += " - "
    err += e.message
    raise EmailingException(err)
    
    
def create_icalendar(request, cal_data, recipients, method):
  
  start_datetime = datetime.datetime.combine(cal_data["date"], cal_data["start_time"])
  duration = datetime.timedelta(minutes=int(cal_data["duration"]))
  url = request.build_absolute_uri("/courts/booking/{booking_id}".format(**cal_data))
  # could use last update timestamp (cal_data["timestamp"]) from
  # the event, except when it is a deletion. For simplicity we
  # will just use the current time - this ensures that the
  # recipient calendar always accepts the event as the latest
  # version
  timestamp = datetime.datetime.now(timezones.UK_TZINFO)
  
  cal = Calendar()
  cal.add("version", "2.0")
  cal.add("prodid", "-//Woking Squash Rackets Club//NONSGML court_booking//EN")
  evt = Event()
  evt.add("uid", "WSRC_booking_{booking_id}".format(**cal_data))
  organizer = vCalAddress("MAILTO:{email}".format(email=BOOKING_SYSTEM_EMAIL_ADRESS))
  organizer.params["cn"] = vText("Woking Squash Club")
  evt.add("organizer", organizer)
  def add_attendee(user):
    attendee = vCalAddress("MAILTO:{email}".format(email=user.email))
    attendee.params["cn"] = vText(user.get_full_name())
    attendee.params["ROLE"] = vText("REQ-PARTICIPANT")
    evt.add('attendee', attendee, encode=0)
  for user in recipients:
    add_attendee(user)

  evt.add("dtstamp", timestamp)    
  evt.add("dtstart", start_datetime)
  evt.add("duration", duration)
  evt.add("summary", "WSRC Court Booking: " + cal_data["name"])
  evt.add("url", url)
  evt.add("location", "Court {court}".format(**cal_data))
  evt.add("description", cal_data.get("description", ""))

  if method == "CANCEL":
    evt.add("status", "CANCELLED")
  cal.add("method", method)

  cal.add_component(evt)
  return cal
    

@require_http_methods(["POST"])
def send_calendar_invite_view(request, id):
  if not request.user.is_authenticated():
    raise PermissionDenied()
  try:
    send_calendar_invite()
  except Exception, e:
    err = ""
    if hasattr(e, "smtp_code"):
      err += "EMAIL SERVER ERROR [{smtp_code:d}] {smtp_error:s} ".format(**e.__dict__)
      if e.message:
        err += " - "
      err += e.message
      raise Exception(err)
  
