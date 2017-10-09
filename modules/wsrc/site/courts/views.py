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
from django.forms.fields import BaseTemporalField
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
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
from wsrc.utils.form_utils import LabeledSelect
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

def query_booking_system(query_params={}, body=None, method="GET", path=settings.BOOKING_SYSTEM_PATH):
  url = settings.BOOKING_SYSTEM_ORIGIN + path + "?" + urllib.urlencode(query_params)
  h = httplib2.Http()
  (resp_headers, content) = h.request(url, method=method, body=body)
  server_time = get_server_time(resp_headers.items())
  if resp_headers.status in (httplib.CREATED, httplib.ACCEPTED):
    return server_time, None
  if resp_headers.status == httplib.OK:
    return server_time, json.loads(content)
  raise RemoteException(content, resp_headers.status)

def auth_query_booking_system(booking_user_id, data={}, query_params={}, method="POST", path=settings.BOOKING_SYSTEM_PATH):
  booking_user_token = BookingSystemEvent.generate_hmac_token_raw("id:{booking_user_id}".format(**locals()))
  data = dict(data)
  data.update({
    "user_id": booking_user_id,
    "user_token": booking_user_token
  })
  return query_booking_system(query_params, json.dumps(data), method, path)

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
    "duration_mins": slot["duration"].total_seconds()/60,
    "court": slot["court"],
    "name": slot["name"],
    "description": slot["description"],
    "type": slot["booking_type"],
    "token": slot["token"],
  }
  return auth_query_booking_system(booking_user_id, data)

def update_booking(booking_user_id, id, slot):
  params = {
    "id": id,
    "method": "PATCH"
  }
  data = {
    "name": slot["name"],
    "description": slot["description"],
    "type": slot["booking_type"],
  }
  return auth_query_booking_system(booking_user_id, data, query_params=params)


def delete_booking(booking_user_id, id):
  params = {
    "id": id,
    "method": "DELETE"
  }
  return auth_query_booking_system(booking_user_id, query_params=params)

def set_noshow(booking_user_id, id, is_noshow):
  params = {
    "id": id,
  }
  method = "POST" if is_noshow else "DELETE"
  return auth_query_booking_system(booking_user_id, query_params=params, path=settings.BOOKING_SYSTEM_NOSHOW, method=method)

def make_booking_link(slot):
  params = {
    'start_time': slot['start_time'],
    'date': timezones.as_iso_date(slot['date']),
    'duration_mins': slot['duration_mins'],
    'court': slot['court'],
    'token': slot['token']
  }
  return '{path}/?{params}'.format(path=reverse_url('booking'), params=urllib.urlencode(params))

def create_booking_cell_content (slot, court, date):
  start_mins = slot["start_mins"]
  start = timezones.to_time(start_mins)
  end   = timezones.to_time(start_mins + slot["duration_mins"])
  result = "<div><div class='slot_time'>{start:%H:%M}&ndash;{end:%H:%M}<br><span class='court'>Court {court}</span></div></a>".format(**locals())
  if "id" in slot:
    result += "<a href='{path}/{id}' data-ajax='false'>{name}</a>".format(path=reverse_url('booking'), id=slot['id'], name=slot['name'])
    if slot.get("no_show"):
      result += '<span class="noshow">NO SHOW</span>'
    
  elif "token" in slot:
    result += "<span class='available'><a href='{href}' data-ajax='false'>(available)</a></span>".format(href=make_booking_link(slot))
  result += "</div>"
  return result
    

def render_day_table(court_slots, date, server_time, allow_booking_shortcut):
  start = START_TIME
  end   = END_TIME
  for (court, slots) in court_slots.iteritems():    
    for slot in slots.itervalues():
      t1 = slot["start_mins"]
      t2 = t1 + slot["duration_mins"]
      start = min(t1, start)
      end   = max(t2, end)
  nrows = (end - start) / RESOLUTION
  attrs = {
    "class": "booking_day",
    "data-server-time": timezones.as_iso_datetime(server_time),
    "data-date": timezones.as_iso_date(date),
    "data-date_str": date.strftime(make_date_formats()[0])
  }
  table = Table(len(COURTS)+2, nrows, attrs)
  for i in range(0,nrows):
    table.addCell(Cell("", attrs={"class": "time-col"}, isHeader=True), 0, i)
    table.addCell(Cell("", attrs={"class": "time-col"}, isHeader=True), 4, i)
  
      
  for court in COURTS:
    slots = court_slots[court]
    row_idx = 0
    slots = slots.values()
    slots.sort(key=operator.itemgetter("start_mins"))
    for slot in slots:
      slot.update({"court": court, "date": date})
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
        for k in ["id"]:
          attrs["data-" + k] = str(slot[k])
        descr = slot.get("description")
        if descr:
          attrs["title"] = descr
      elif "token" in slot:
        attrs["title"] = 'click to book' 
        if allow_booking_shortcut:
          attrs["onclick"] = "wsrc.court_booking.instance.handle_booking_request(event, this)"
        else:
          attrs["onclick"] = "document.location.href='{href}'".format(href=make_booking_link(slot))
        classes.append("available")
        for k in ["token", "start_time", "duration_mins"]:
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
  table_head = "<thead><tr><td class='time-col'></td>{courts}<td class='time-col'></td></tr></thead>".format(courts=court_headers)  
  return table.toHtmlString(table_head)


@require_safe
def day_view(request, date=None):
    if date is None:
        date = datetime.date.today()
    else:
        date = timezones.parse_iso_date_to_naive(date)
    player = Player.get_player_for_user(request.user)
    booking_user_id = None if player is None else player.booking_system_id    
    server_time, bookings = get_bookings(date)
    table_html = render_day_table(bookings, date, server_time, booking_user_id is not None)
    if request.GET.get("table_only") is not None:
      return HttpResponse(table_html)
    context = {
      "date": date,
      "prev_date": date - datetime.timedelta(days=1),
      "next_date": date + datetime.timedelta(days=1),
      "day_table": table_html,
      "booking_user_name": request.user.get_full_name() if booking_user_id is not None else '' 
    }    
    return render(request, 'courts.html', context)

def validate_15_minute_multiple(value):
  rem = value % 15
  if rem != 0:
    raise ValidationError("{value} is not a 15-minute multiple".format(**locals()))

def validate_quarter_hour(value):
  if value.second != 0 or value.microsecond != 0:
    raise ValidationError("{value} has less than minute resolution".format(**locals()))
  validate_15_minute_multiple(value.minute)

def validate_quarter_hour_duration(value):
  value = value.total_seconds()  
  if (value % 60) != 0:
    raise ValidationError("{value} has less than minute resolution".format(**locals()))
  validate_15_minute_multiple(value/60)

def make_readonly_widget():
  return forms.TextInput(attrs={'class': 'readonly', 'readonly': 'readonly', 'style': 'text-align: left'})

def make_date_formats():
  return ['%a %d %b %Y', '%Y-%m-%d']

def make_datetime_formats():
  return [x + " %H:%M:%S" for x in make_date_formats()]
  
def format_date(val, fmts):
  v = datetime.datetime.strptime(val, fmts[1])
  return v.strftime(fmts[0])

class HourAndMinuteDurationField(BaseTemporalField):
  default_error_messages = {
    'required': 'This field is required.',
    'invalid': 'Enter a valid duration.',
  }
  def strptime(self, value, format):
    return timezones.parse_duration(value)
  def to_python(self, value):
    if value in self.empty_values:
      return None
    return super(HourAndMinuteDurationField, self).to_python(value)

class BookingForm(forms.Form):
  name = forms.CharField(max_length=80)
  description = forms.CharField(required=False, widget=forms.TextInput(attrs={'autofocus': 'autofocus'}))

  date = forms.DateField(input_formats=make_date_formats())
  start_time = forms.TimeField(label="Time", input_formats=['%H:%M'], validators=[validate_quarter_hour],
                               widget=forms.Select(choices=[(t.strftime("%H:%M"), t.strftime("%H:%M")) for t in START_TIMES]))
  duration = HourAndMinuteDurationField(validators=[validate_quarter_hour_duration], input_formats=[None],
                                        widget=forms.Select(choices=[(timezones.duration_str(i), timezones.duration_str(i)) for i in DURATIONS]))
  court = forms.ChoiceField(choices=[(i, str(i)) for i in COURTS])
  booking_type = forms.ChoiceField(choices=[("I", "Member"), ("E", "Club")])

  created_by = forms.CharField(max_length=80, label="Created By", widget=make_readonly_widget(), required=False)
  created_ts = forms.DateTimeField(label="Created At", input_formats=make_datetime_formats(), widget=make_readonly_widget(), required=False)
  timestamp  = forms.DateTimeField(label="Last Updated", input_formats=make_datetime_formats(), widget=make_readonly_widget(), required=False)
  
  booking_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
  created_by_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
  token = forms.CharField(required=False, widget=forms.HiddenInput())
  no_show = forms.BooleanField(required=False, widget=forms.HiddenInput())

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
    slot["duration"] = timezones.duration_str(datetime.timedelta(minutes=slot["duration"]))
    return slot

  @staticmethod
  def transform_booking_system_deleted_entry(entry):
    timestamp = datetime.datetime.utcfromtimestamp(int(entry["start_time"]))
    timestamp = timezones.naive_utc_to_local(timestamp, timezones.UK_TZINFO)
    duration = datetime.timedelta(seconds=(int(entry["end_time"]) - int(entry["start_time"])))
    data = {
      "date": timestamp.date(),
      "start_time": timestamp.time(),
      "duration": duration,
      "court": entry["room_id"],
      "name": entry["name"],
      "description": entry["description"],
    }
    return data

  @staticmethod
  def empty_form(error=None):
    booking_form = BookingForm(empty_permitted=True,data={})
    booking_form.is_valid() # initializes cleaned_data
    if error is not None:
      booking_form.add_error(None, error)
    return booking_form

def edit_entry_view(request, id=None):
  player = Player.get_player_for_user(request.user)
  booking_user_id = None if player is None else player.booking_system_id
  method = request.method
  booking_form = None
  server_time = datetime.datetime.now()
  
  if method == "POST":
    action = request.REQUEST.get("action") or ""
    if action.upper() == "DELETE":
      method = "DELETE"
    elif action.upper() in ("UPDATE", "REPORT_NOSHOW", "REMOVE_NOSHOW"):
      method = "PATCH"

  if method == "POST":
    booking_form = BookingForm(request.REQUEST)
    if booking_user_id is None:
      raise SuspiciousOperation()
    if booking_form.is_valid():
      try:
        server_time, new_booking = create_booking(booking_user_id, booking_form.cleaned_data)
        booking_data = dict(booking_form.cleaned_data)
        id = booking_data["booking_id"] = new_booking.get("id")
        send_calendar_invite(request, booking_data, [request.user], "create")
        return redirect(reverse_url(day_view) + "/" + timezones.as_iso_date(booking_form.cleaned_data["date"]))
      except RemoteException, e:
        booking_form.add_error(None, str(e))
      except EmailingException, e:
        booking_form.add_error(None, str(e))

  elif method == "DELETE":
    booking_form = BookingForm(request.REQUEST)
    if id is None or booking_user_id is None:
      raise SuspiciousOperation()
    try:
      server_time, data = delete_booking(booking_user_id, id)
      data = BookingForm.transform_booking_system_deleted_entry(data)
      data["booking_id"] = id
      send_calendar_invite(request, data, [request.user], "delete")
      return redirect(request.POST.get("next"))
    except RemoteException, e:
      if e.status == httplib.NOT_FOUND:
        id = None
        error = "Booking not found - has it already been deleted?"
        booking_form = BookingForm.empty_form(error)
      else:
        error = str(e)
        booking_form = add_error(error)
    except EmailingException, e:
      booking_form.add_error(None, str(e))

  elif method == "PATCH":
    booking_form = BookingForm(dict(request.REQUEST))
    if id is None or booking_user_id is None:
      raise SuspiciousOperation()
    try:
      if request.POST.get("action") == "report_noshow":
        server_time, data = set_noshow(booking_user_id, id, True)
        booking_form.data["no_show"] = True
        booking_form.is_valid()
      elif request.POST.get("action") == "remove_noshow":
        server_time, data = set_noshow(booking_user_id, id, False)
        booking_form.data["no_show"] = False
        booking_form.is_valid()
      else:
        if booking_form.is_valid():
          server_time, data = update_booking(booking_user_id, id, booking_form.cleaned_data)
          send_calendar_invite(request, booking_form.cleaned_data, [request.user], "update")
          back = reverse_url(day_view) + "/" + timezones.as_iso_date(booking_form.cleaned_data["date"])        
          return redirect(back)
    except RemoteException, e:
      if e.status == httplib.NOT_MODIFIED:
        back = reverse_url(day_view) + "/" + timezones.as_iso_date(booking_form.cleaned_data["date"])        
        return redirect(back)
      if e.status == httplib.NOT_FOUND:
        id = None
        error = "Booking not found - has it already been deleted?"
        booking_form = BookingForm.empty_form(error)
      else:
        booking_form.add_error(None, str(e))
    except EmailingException, e:
      booking_form.add_error(None, error)

  elif method == "GET":
    if id is None:
      if not request.user.is_authenticated():
        return redirect('/login/?next=%s' % urllib.quote(request.get_full_path()))
      initial_data = {
        'name': request.user.get_full_name(),
        'booking_type': 'I'
      }
      def get(field):
        val = request.GET.get(field)
        if val is None:
          raise SuspiciousOperation("missing booking data for '{field}'".format(**locals()))
        return val
      for field in ['date', 'start_time', 'court', 'token']:
        val = get(field)
        if field == 'date':
          val = format_date(val, make_date_formats())
        initial_data[field] = val
      val = get("duration_mins")
      initial_data["duration"] = timezones.duration_str(datetime.timedelta(minutes=int(val)))
      booking_form = BookingForm(data=initial_data)
      if booking_user_id is None:
        link = settings.BOOKING_SYSTEM_ORIGIN + "/day.php"
        if booking_form.is_valid():
          link += "?year={date:%Y}&month={date:%m}&day={date:%d}&area=1".format(date=booking_form.cleaned_data["date"])
        error = """Sorry, your login is not set up to book courts from this website.
        Please contact <a href='mailto:webmaster@wokingsquashclub.org'>webmaster@wokingsquashclub.org</a> 
        to get this fixed, and use the <a href='{link}'>old booking site</a> in the meantime.
        """.format(link=link)
        booking_form.add_error(None, error)            
    else:
      server_time, booking_data = get_booking(id)
      if booking_data is None:
        error = "Booking not found - has it already been deleted?"
        booking_form = BookingForm.empty_form(error)
        id = None
      else:
        initial_data = BookingForm.transform_booking_system_entry(booking_data)
        booking_form = BookingForm(data=initial_data)

  
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
    if booking_user_id is not None and \
       booking_form.is_valid() and \
       booking_user_id == booking_form.cleaned_data.get("created_by_id") \
       and (days_diff < 0 or (days_diff == 0 and seconds_diff < 0)):
      mode = "update"
    elif is_admin:
      mode = "update"
      readonly_fields.remove("name")
      hidden_fields.remove("booking_type")
    else:
      readonly_fields.append("description")
  

  for field in readonly_fields:    
    booking_form.fields[field].widget = make_readonly_widget()
  for field in hidden_fields:
    booking_form.fields[field].widget = forms.HiddenInput()

  back = request.REQUEST.get("next")
  if back is None:
    if booking_form.is_valid():
      back = reverse_url(day_view)
      back += "/" + timezones.as_iso_date(booking_form.cleaned_data["date"])
    else:
      back = reverse_url(day_view)      

  context = {
    'booking_form': booking_form,
    'mode': mode,
    'back_url':  back,
    'days_diff': days_diff,
    'seconds_diff': seconds_diff,
    'booking_id': id,
    'booking_user_id': booking_user_id    
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
  duration = cal_data["duration"]
  url = request.build_absolute_uri("/courts/booking/{booking_id}".format(**cal_data))
  # could use last update timestamp (cal_data["timestamp"]) from
  # the event, except when it is a deletion. For simplicity we
  # will just use the current time - this ensures that the
  # recipient calendar always accepts the event as the latest
  # version
  timestamp = datetime.datetime.now(timezones.UK_TZINFO)
  summary = cal_data.get("summary")
  if summary is None:
    summary = CalendarInviteForm.get_summary(cal_data)
  location = cal_data.get("location")
  if location is None:
    location = CalendarInviteForm.get_location(cal_data)
  
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
  evt.add("summary", summary)
  evt.add("url", url)
  evt.add("location", location)
  evt.add("description", cal_data.get("description", ""))

  if method == "CANCEL":
    evt.add("status", "CANCELLED")
  cal.add("method", method)

  cal.add_component(evt)
  return cal

def get_active_player_choices():
  return [(None, '')] + [(u.id, u.get_full_name()) for u in User.objects.filter(is_active=True).filter(player__isnull=False).order_by('first_name', 'last_name')]

class CalendarInviteForm(forms.Form):
  summary = forms.CharField(label="Summary", max_length=80, widget=make_readonly_widget())
  description = forms.CharField(required=False)
  date = forms.DateField(input_formats=make_date_formats(), widget=make_readonly_widget())
  start_time = forms.TimeField(label="Time", input_formats=['%H:%M'], validators=[validate_quarter_hour],
                               widget=make_readonly_widget())
  duration = HourAndMinuteDurationField(validators=[validate_quarter_hour_duration], input_formats=[None],
                                        widget=make_readonly_widget())
  location = forms.CharField(widget=make_readonly_widget())
  booking_id = forms.IntegerField(widget=forms.HiddenInput())
  court = forms.IntegerField(widget=forms.HiddenInput())
  invitee_1 = forms.ChoiceField(choices=get_active_player_choices(), widget=LabeledSelect(attrs={'disabled': 'disabled', 'class': 'readonly'}))
  invitee_2 = forms.ChoiceField(choices=get_active_player_choices(), widget=LabeledSelect(attrs={'autofocus': 'autofocus'}))
  invitee_3 = forms.ChoiceField(choices=get_active_player_choices(), widget=LabeledSelect, required=False)
  invitee_4 = forms.ChoiceField(choices=get_active_player_choices(), widget=LabeledSelect, required=False)

  @staticmethod
  def get_location(booking_data):
    return "Court {court}, Woking Squash Club, Horsell Moor, Woking GU21 4NR".format(**booking_data)    

  @staticmethod
  def get_summary(booking_data):
    return "WSRC Court Booking - {name}".format(**booking_data)
  
@login_required
def calendar_invite_view(request, id):
  if request.method == "POST":
    data = dict(request.REQUEST)
    data["invitee_1"] = request.user.id
    form = CalendarInviteForm(data)
    if form.is_valid():
      try:
        invitees = []
        for i in range(1,4):
          user_id = form.cleaned_data.get("invitee_{i}".format(i=i))
          if user_id is not None and len(user_id) > 0:
            invitees.append(User.objects.get(pk=user_id)) 
        send_calendar_invite(request, form.cleaned_data, invitees, "update")
        back = reverse_url(day_view) + "/" + timezones.as_iso_date(form.cleaned_data["date"])
        return redirect(back)
      except EmailingException, e:
        form.add_error(None, str(e))
        
  else:
    server_time, booking_data = get_booking(id)
    if booking_data is None:
      error = "Booking not found - has it already been deleted?"
      form = CalendarInviteForm(empty_permitted=True)
      form.is_valid() # initializes cleaned_data
      form.add_error(None, error)
    else:
      created_by_id = booking_data["created_by_id"]
      booking_data = BookingForm.transform_booking_system_entry(booking_data)
      booking_data["location"] = CalendarInviteForm.get_location(booking_data)
      booking_data["summary"] = CalendarInviteForm.get_summary(booking_data)
      booking_data["invitee_1"] = request.user.id
      try:
        court_booker = Player.objects.get(booking_system_id = created_by_id)
        if court_booker.user.id != request.user.id:
          booking_data["invitee_2"] = court_booker.user.id
      except Player.DoesNotExist:
        pass
      form = CalendarInviteForm(initial=booking_data)
      
  context = {
    'form': form,
    'id': id,
    'back_url': reverse_url('booking') + "/{id}".format(**locals()),
  }
  return render(request, 'cal_invite.html', context)
  
