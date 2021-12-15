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
import json
import logging
import operator
import urllib

import httplib2
import pytz
from django import forms
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import SuspiciousOperation, PermissionDenied, ValidationError
from django.core.mail import SafeMIMEMultipart, SafeMIMEText
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponsePermanentRedirect, HttpResponseNotFound
from django.shortcuts import redirect, get_object_or_404
from django.template.response import TemplateResponse
from django.urls import reverse as reverse_url, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_safe
from django.views.generic.edit import CreateView
from icalendar import Calendar, Event, vCalAddress, vText, parser_tools

import wsrc.site.settings.settings as settings
from wsrc.site.courts.models import BookingSystemEvent, EventFilter, BookingOffence
from wsrc.site.usermodel.models import Player
from wsrc.utils import timezones, email_utils
from wsrc.utils.form_utils import make_readonly_widget, add_formfield_attrs
from wsrc.utils.html_table import Table, Cell, SpanningCell
from .court_slot_utils import add_free_slots
from .forms import START_TIME, END_TIME, RESOLUTION, COURTS, \
    format_date, make_date_formats, create_notifier_filter_formset_factory, \
    BookingForm, CalendarInviteForm, CondensationReportForm, using_local_database

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.WARNING)

BOOKING_SYSTEM_EMAIL_ADDRESS = "court_booking@wokingsquashclub.org"


class RemoteException(Exception):
    def __init__(self, body, status):
        msg = "Error {code} [{name}] - {body}".format(code=status, name=httplib.responses[status], body=body)
        super(RemoteException, self).__init__(msg)
        self.status = status
        self.body = body


class EmailingException(Exception):
    pass


def get_server_time(headers):
    for (key, val) in headers:
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


def auth_query_booking_system(booking_user_id, data={}, query_params={}, method="POST",
                              path=settings.BOOKING_SYSTEM_PATH):
    booking_user_token = BookingSystemEvent.generate_hmac_token_raw("id:{booking_user_id}".format(**locals()))
    data = dict(data)
    data.update({
        "user_id": booking_user_id,
        "user_token": booking_user_token
    })
    return query_booking_system(query_params, json.dumps(data), method, path)


def get_bookings(date, ignore_cutoff=False):
    if using_local_database():
        MIDNIGHT_NAIVE = datetime.time()
        date = timezone.make_aware(datetime.datetime.combine(date, MIDNIGHT_NAIVE))
        booked_slots = BookingSystemEvent.get_bookings_for_date(date)
        now = timezone.localtime(timezone.now())
        results = dict([(court, []) for court in COURTS])
        for booked_slot in booked_slots:
            results[booked_slot.court].append(booked_slot)
        for court in COURTS:
            booked_slots = results[court]
            add_free_slots(court, booked_slots, date, now, ignore_cutoff)
            results[court] = dict([(slot["start_mins"], slot) for slot in booked_slots])
        return now, results
    today_str = timezones.as_iso_date(date)
    tomorrow_str = timezones.as_iso_date(date + datetime.timedelta(days=1))
    params = {
        "start_date": today_str,
        "end_date": tomorrow_str,
        "with_tokens": 1
    }
    server_time, data = query_booking_system(params)
    courts = data[today_str]
    return server_time, dict([(int(i), v) for i, v in courts.iteritems()])


def get_booking_form_data(id):
    if using_local_database():
        now = timezone.localtime(timezone.now())
        booking_data = get_object_or_404(BookingSystemEvent, pk=id, is_active=True)
        booking_data = BookingForm.transform_booking_model(booking_data)
        return now, booking_data
    params = {
        "id": id,
        "with_tokens": 1
    }
    server_time, data = query_booking_system(params)
    result = None
    if data is not None and len(data) > 0:
        for date, courts in data.iteritems():
            for court, start_times in courts.iteritems():
                for start_time, slot in start_times.iteritems():
                    slot["court"] = int(court)
                    slot["date"] = date
                    result = slot
    booking_data = BookingForm.transform_booking_system_entry(result)
    return server_time, booking_data


@transaction.atomic
def create_booking(user, slot, is_admin_view=False):
    if using_local_database():
        now = timezone.localtime(timezone.now())
        model = BookingForm.transform_to_booking_system_event(slot)
        if not is_admin_view and model.hmac_token() != slot.get("token"):
            raise ValidationError("Incorrect token supplied")
        model.created_by_user = user
        model.last_updated_by = user
        model.created_time = now
        model.validate_unique([])
        model.save()
        return now, model

    player = Player.get_player_for_user(user)
    booking_user_id = None if player is None else player.booking_system_id
    if booking_user_id is None:
        raise SuspiciousOperation()

    start_time = slot["start_time"]
    data = {
        "date": timezones.as_iso_date(slot["date"]),
        "start_mins": start_time.hour * 60 + start_time.minute,
        "duration_mins": slot["duration"].total_seconds() / 60,
        "court": slot["court"],
        "name": slot["name"],
        "description": slot["description"],
        "type": slot["booking_type"],
        "token": slot["token"],
    }
    return auth_query_booking_system(booking_user_id, data)


@transaction.atomic
def update_booking(user, event_id, booking_form):
    if event_id is None:
        raise SuspiciousOperation()

    if using_local_database():
        model = get_object_or_404(BookingSystemEvent, pk=event_id, is_active=True)
        if not (model.is_writable_by_user(user) or has_admin_permission(user, False)):
            raise PermissionDenied()
        slot = booking_form.cleaned_data
        model.name = slot["name"]
        model.opponent = slot["opponent"]
        model.description = slot["description"]
        model.event_type = slot["booking_type"]
        model.last_updated_by = user
        model.save()
        now = timezone.localtime(timezone.now())
        return now, model

    slot = booking_form.cleaned_data
    player = Player.get_player_for_user(user)
    booking_user_id = None if player is None else player.booking_system_id
    if booking_user_id is None:
        raise SuspiciousOperation()

    params = {
        "id": event_id,
        "method": "PATCH"
    }
    data = {
        "name": slot["name"],
        "description": slot["description"],
        "type": slot["booking_type"],
    }
    return auth_query_booking_system(booking_user_id, data, query_params=params)


@transaction.atomic
def delete_booking(user, event_id):
    if event_id is None:
        raise SuspiciousOperation()

    if using_local_database():
        model = get_object_or_404(BookingSystemEvent, pk=event_id, is_active=True)
        if not (model.is_writable_by_user(user) or has_admin_permission(user, False)):
            raise PermissionDenied()
        start_time = model.start_time.astimezone(timezones.UK_TZINFO)
        cal_invite_data = {
            "date": start_time.date(),
            "start_time": start_time.time(),
            "court": model.court,
            "name": model.name,
            "description": model.description,
            "duration": model.duration,
            "booking_id": model.pk,
        }
        model.last_updated_by = user
        model.is_active = False
        model.save()
        now = timezone.localtime(timezone.now())
        return now, cal_invite_data

    player = Player.get_player_for_user(user)
    booking_user_id = None if player is None else player.booking_system_id
    if booking_user_id is None:
        raise SuspiciousOperation()
    params = {
        "id": event_id,
        "method": "DELETE"
    }
    timestamp, data = auth_query_booking_system(booking_user_id, query_params=params)
    data = BookingForm.transform_booking_system_deleted_entry(data)
    data["booking_id"] = event_id
    return timestamp, data


def set_noshow(user, event_id, is_noshow):
    if using_local_database():
        model = get_object_or_404(BookingSystemEvent, pk=event_id, is_active=True)
        now = timezone.localtime(timezone.now())
        if is_noshow:
            if model.no_show:
                raise SuspiciousOperation()
            delta_t = now - model.start_time
            if delta_t.total_seconds() < (15 * 60):
                raise PermissionDenied("cannot report noshow less than 15 minutes after start time")
            model.no_show = True
            model.no_show_reporter = user
        else:
            if not model.no_show:
                raise SuspiciousOperation()
            if user != model.no_show_reporter and (not user.is_superuser):
                raise PermissionDenied("not authorized to change this entry")
            model.no_show = False
            model.no_show_reporter = None
        model.save()
        return now, model

    player = Player.get_player_for_user(user)
    booking_user_id = None if player is None else player.booking_system_id
    if booking_user_id is None:
        raise SuspiciousOperation()
    params = {
        "id": event_id,
    }
    method = "POST" if is_noshow else "DELETE"
    return auth_query_booking_system(booking_user_id, query_params=params, path=settings.BOOKING_SYSTEM_NOSHOW,
                                     method=method)


def make_booking_link(slot, court, date, is_admin_view=False):
    params = {
        'start_time': slot['start_time'],
        'date': timezones.as_iso_date(date),
        'duration_mins': slot['duration_mins'],
        'court': court,
        'token': slot['token']
    }
    url_name = 'booking_admin' if is_admin_view else 'booking'
    return '{path}/?{params}'.format(path=reverse_url(url_name), params=urllib.urlencode(params))


def create_booking_cell_content(slot, court, date, is_admin_view=False):
    start_mins = slot["start_mins"]
    start = timezones.to_time(start_mins)
    end = timezones.to_time(start_mins + slot["duration_mins"])
    result = "<div><div class='slot_time'>{start:%H:%M}&ndash;{end:%H:%M}</div>".format(**locals())
    if "id" in slot:
        url_name = 'booking_admin' if is_admin_view else 'booking'
        opponent = slot["opponent"]
        content = slot['name']
        if slot["type"] == "I":
            if opponent is None:
                content += "<span class='no_opponent label label-danger'>No Opponent</span>"
            elif opponent == "Solo":
                content += " [Solo&nbsp;Practice]"
            elif opponent == "_Coaching_":
                content += " [Coaching]"
            else:
                content += " vs " + opponent
        result += u"<span class='booking'><a href='{path}/{id}'>{content}</a></span>".format(path=reverse_url(url_name),
                                                                                          id=slot['id'],
                                                                                          content=content)
        if slot.get("no_show"):
            result += '<div class="noshow label label-danger">NO SHOW</div>'

    elif "token" in slot:
        result += "<span class='available'><a href='{href}'>(available)</a></span>".format(
            href=make_booking_link(slot, court, date, is_admin_view))
    result += "</div>"
    return result


def render_day_table(court_slots, date, server_time, allow_booking_shortcut, is_admin_view=False):
    start = START_TIME
    end = END_TIME
    for (court, slots) in court_slots.iteritems():
        for slot in slots.itervalues():
            t1 = slot["start_mins"]
            t2 = t1 + slot["duration_mins"]
            start = min(t1, start)
            end = max(t2, end)
    nrows = (end - start) / RESOLUTION
    attrs = {
        "class": "booking_day",
        "data-server-time": timezones.as_iso_datetime(server_time),
        "data-date": timezones.as_iso_date(date),
        "data-date_str": date.strftime(make_date_formats()[0])
    }
    table = Table(len(COURTS) + 2, nrows, attrs)
    for i in range(0, nrows):
        table.addCell(Cell("", attrs={"class": "time-col"}, isHeader=True), 0, i)
        table.addCell(Cell("", attrs={"class": "time-col"}, isHeader=True), 4, i)

    booking_path = reverse_url('booking')
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
            nrows = duration_mins / RESOLUTION
            attrs = {"data-court": str(court)}
            classes = ["slot"]
            admin_prefix = "/admin" if is_admin_view else ""
            if "id" in slot:
                attrs['onclick'] = "document.location.href='{path}{prfx}/{id}'".format(path=booking_path,
                                                                                       prfx=admin_prefix, id=slot['id'])
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
                    attrs["onclick"] = "handle_booking_request(event, this)"
                else:
                    attrs["onclick"] = "document.location.href='{href}'" \
                        .format(href=make_booking_link(slot, court, date, is_admin_view))
                classes.append("available")
                for k in ["token", "start_time", "duration_mins"]:
                    attrs["data-" + k] = str(slot[k])
            attrs["class"] = " ".join(classes)
            content = create_booking_cell_content(slot, court, date, is_admin_view)
            cell = SpanningCell(1, nrows, content=content, attrs=attrs, isHTML=True)
            table.addCell(cell, court, row_idx)
            row_idx += nrows
            last_cell = cell
        last_cell.attrs["class"] += " column-last"
    last_cell.attrs["class"] += " last"

    table.compress()
    court_headers = "".join(["<th>Court {d}</th>".format(d=court) for court in COURTS])
    table_head = "<thead><tr><td class='time-col'></td>{courts}<td class='time-col'></td></tr></thead>"\
        .format(courts=court_headers)
    return table.toHtmlString(table_head)


def has_admin_permission(user, raise_exception=True):
    if user.has_perm("courts.add_bookingsystemevent") and \
            user.has_perm("courts.add_bookingsystemevent") and \
            user.has_perm("courts.add_bookingsystemevent"):
        return True
    if raise_exception:
        raise PermissionDenied("You are not authorized to edit court bookings")
    return False


@require_safe
@user_passes_test(has_admin_permission)
def day_view_admin(request, date):
    return day_view(request, date, True)


@require_safe
def day_view(request, date=None, is_admin_view=False):
    if date is None:
        date = datetime.date.today()
    else:
        date = timezones.parse_iso_date_to_naive(date)
    player = Player.get_player_for_user(request.user)
    booking_user_id = None if player is None else player.booking_system_id
    server_time, bookings = get_bookings(date, ignore_cutoff=is_admin_view)
    allow_booking_shortcut = settings.BOOKING_SYSTEM_SETTINGS.get("allow_booking_shortcut") and \
                             booking_user_id is not None
    if is_admin_view:
        allow_booking_shortcut = False
    table_html = render_day_table(bookings, date, server_time, allow_booking_shortcut, is_admin_view)
    if request.GET.get("table_only") is not None:
        return HttpResponse(table_html)
    context = {
        "date": date,
        "prev_date": date - datetime.timedelta(days=1),
        "next_date": date + datetime.timedelta(days=1),
        "day_table": table_html,
        "booking_user_name": request.user.get_full_name() if booking_user_id is not None else '',
        "court_admin": has_admin_permission(request.user, raise_exception=False),
        "is_admin_view": is_admin_view
    }
    return TemplateResponse(request, 'courts.html', context)


def day_view_redirect(request, date=None):
    url = reverse_url(day_view)
    if date is not None:
        url += "/" + date
    return HttpResponsePermanentRedirect(url)


@user_passes_test(has_admin_permission)
def edit_entry_admin_view(request, id=None):
    return edit_entry_view(request, id, is_admin_view=True)


@login_required
def edit_entry_view(request, event_id=None, is_admin_view=False):
    player = Player.get_player_for_user(request.user)
    booking_user_id = None if player is None else player.booking_system_id
    method = request.method
    booking_form = None
    server_time = datetime.datetime.now()
    response_code = httplib.OK
    reverse_view = day_view_admin if is_admin_view else day_view

    if method == "POST":
        action = request.POST.get("action") or ""
        if action.upper() == "DELETE":
            method = "DELETE"
        elif action.upper() in ("UPDATE", "REPORT_NOSHOW", "REMOVE_NOSHOW"):
            method = "PATCH"

    if method == "POST":
        booking_form = BookingForm(request.POST)
        if booking_form.is_valid():
            opponent = booking_form.cleaned_data["opponent"]
            if settings.BOOKING_SYSTEM_SETTINGS.get("require_opponent") and \
                    opponent is None or len(opponent) == 0:
                booking_form.add_error("opponent", "Please enter the name of your opponent, or 'Solo Practice'")
                booking_form.is_retry = True
                response_code = httplib.FORBIDDEN
            else:
                try:
                    server_time, new_booking = create_booking(request.user, booking_form.cleaned_data, is_admin_view)
                    booking_data = dict(booking_form.cleaned_data)
                    event_id = booking_data["booking_id"] = new_booking.get("id")
                    send_calendar_invite(request, booking_data, [request.user], "create")
                    return redirect(reverse_url(reverse_view, args=[booking_form.cleaned_data["date"]]))
                except ValidationError, e:
                    booking_form.add_error(None, ", ".join(e.messages))
                    response_code = httplib.CONFLICT
                except RemoteException, e:
                    booking_form.add_error(None, str(e))
                    response_code = httplib.CONFLICT
                except EmailingException, e:
                    booking_form.add_error(None, str(e))
                    response_code = httplib.SERVICE_UNAVAILABLE

    elif method == "DELETE":
        booking_form = BookingForm(request.POST)
        if event_id is None:
            raise SuspiciousOperation()
        try:
            server_time, data = delete_booking(request.user, event_id)
            send_calendar_invite(request, data, [request.user], "delete")
            return redirect(request.POST.get("next"))
        except RemoteException, e:
            if e.status == httplib.NOT_FOUND:
                event_id = None
                error = "Booking not found - has it already been deleted?"
                booking_form = BookingForm.empty_form(error)
            else:
                error = str(e)
                booking_form.add_error(error)
        except EmailingException, e:
            booking_form.add_error(None, str(e))

    elif method == "PATCH":
        booking_form = BookingForm(request.POST)
        if event_id is None:
            raise SuspiciousOperation()
        try:
            if request.POST.get("action") == "report_noshow":
                server_time, model = set_noshow(request.user, event_id, True)
                booking_data = BookingForm.transform_booking_model(model)
                booking_form = BookingForm(data=booking_data)
            elif request.POST.get("action") == "remove_noshow":
                server_time, model = set_noshow(request.user, event_id, False)
                booking_data = BookingForm.transform_booking_model(model)
                booking_form = BookingForm(data=booking_data)
            else:
                if booking_form.is_valid():
                    server_time, data = update_booking(request.user, event_id, booking_form)
                    send_calendar_invite(request, booking_form.cleaned_data, [request.user], "update")
                    back = reverse_url(reverse_view, args=[booking_form.cleaned_data["date"]])
                    return redirect(back)
        except RemoteException, e:
            if e.status == httplib.NOT_MODIFIED:
                back = reverse_url(day_view, booking_form.cleaned_data["date"])
                return redirect(back)
            if e.status == httplib.NOT_FOUND:
                event_id = None
                error = "Booking not found - has it already been deleted?"
                booking_form = BookingForm.empty_form(error)
            else:
                booking_form.add_error(None, str(e))
        except EmailingException, e:
            booking_form.add_error(None, e)

    elif method == "GET":
        if event_id is None:
            if not request.user.is_authenticated():
                return redirect('/login/?next=%s' % urllib.quote(request.get_full_path()))
            if is_admin_view:
                initial_data = {
                    'name': "Club Booking",
                    'booking_type': 'E'
                }
            else:
                initial_data = {
                    'name': request.user.get_full_name(),
                    'opponent': None,
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
            if is_admin_view:
                booking_form.set_admin()
            if booking_user_id is None and not using_local_database():
                link = settings.BOOKING_SYSTEM_ORIGIN + "/day.php"
                if booking_form.is_valid():
                    link += "?year={date:%Y}&month={date:%m}&day={date:%d}&area=1".format(
                        date=booking_form.cleaned_data["date"])
                error = """Sorry, your login is not set up to book courts from this website.
                Please contact <a href='mailto:webmaster@wokingsquashclub.org'>webmaster@wokingsquashclub.org</a>
                to get this fixed, and use the <a href='{link}'>old booking site</a> in the meantime.
                """.format(link=link)
                booking_form.add_error(None, error)
        else:
            server_time, booking_data = get_booking_form_data(event_id)
            if booking_data is None:
                error = "Booking not found - has it already been deleted?"
                booking_form = BookingForm.empty_form(error)
                event_id = None
            else:
                booking_form = BookingForm(data=booking_data)

    if is_admin_view:
        readonly_fields = []
        hidden_fields = []
    else:
        readonly_fields = ['name', 'date', 'start_time', 'duration', 'court']
        hidden_fields = ['booking_type']

    days_diff = seconds_diff = None
    is_future_event = False
    if event_id is None:
        mode = "create"
        hidden_fields.extend(['created_ts', 'created_by', 'timestamp'])
    else:
        mode = "view"
        if booking_form.is_valid():
            days_diff = server_time.date().toordinal() - booking_form.cleaned_data['date'].toordinal()
            seconds_diff = timezones.to_seconds(server_time.time()) - timezones.to_seconds(
                booking_form.cleaned_data['start_time'])
            is_future_event = (days_diff < 0 or (days_diff == 0 and seconds_diff < 0))
        if is_admin_view:
            mode = "update"
            readonly_fields = ['date', 'start_time', 'duration', 'court']
        elif is_future_event and booking_form.is_authorized(request.user):
            mode = "update"
        else:
            readonly_fields.append("description")

    for field in readonly_fields:
        booking_form.fields[field].widget = make_readonly_widget()
    for field in hidden_fields:
        booking_form.fields[field].widget = forms.HiddenInput()
    add_formfield_attrs(booking_form)

    back = request.POST.get("next", request.GET.get("next"))
    if back is None:
        if booking_form.is_valid():
            back = reverse_url(reverse_view, args=[booking_form.cleaned_data["date"]])
        else:
            back = reverse_url(day_view)

    context = {
        'booking_form': booking_form,
        'mode': mode,
        'back_url': back,
        'days_diff': days_diff,
        'seconds_diff': seconds_diff,
        'booking_id': event_id,
        'booking_user_id': booking_user_id,
        'is_admin_view': is_admin_view,
    }
    return TemplateResponse(request, 'booking.html', context, status=response_code)


def send_calendar_invite(request, slot, recipients, event_type):
    method = "CANCEL" if event_type == "delete" else "REQUEST"
    cal = create_icalendar(request, slot, recipients, method)
    encoding = settings.DEFAULT_CHARSET
    cal_encoding = parser_tools.DEFAULT_ENCODING
    cal_body_unicode = cal.to_ical().decode(cal_encoding)
    msg_cal = SafeMIMEText(cal_body_unicode, "calendar", encoding)
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
    subject = "WSRC Court Booking - {date:%Y-%m-%d} {start_time:%H:%M} Court {court}".format(**slot)
    try:
        email_utils.send_email(subject, "", None,
                               from_address=BOOKING_SYSTEM_EMAIL_ADDRESS,
                               to_list=to_list, cc_list=None,
                               extra_attachments=[msg_bodies, msg_cal])
    except Exception, e:
        LOGGER.exception("unable to send email")
        err = ""
        if hasattr(e, "smtp_code"):
            err += "EMAIL SERVER ERROR [{smtp_code:d}] {smtp_error:s} ".format(**e.__dict__)
            if e.message:
                err += " - "
        err += e.message
        raise EmailingException(err)


def create_icalendar(request, cal_data, recipients, method):
    start_datetime = datetime.datetime.combine(cal_data["date"], cal_data["start_time"])
    start_datetime = start_datetime.replace(tzinfo=pytz.timezone("Europe/London"))
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
    cal.add_component(timezones.create_icalendar_uk_timezone())

    evt = Event()
    evt.add("uid", "WSRC_booking_{booking_id}".format(**cal_data))
    organizer = vCalAddress("MAILTO:{email}".format(email=BOOKING_SYSTEM_EMAIL_ADDRESS))
    organizer.params["cn"] = vText("Woking Squash Club")
    evt.add("organizer", organizer)

    def add_attendee(user_obj):
        attendee = vCalAddress("MAILTO:{email}".format(email=user_obj.email))
        attendee.params["cn"] = vText(user_obj.get_full_name())
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


@login_required
def calendar_invite_view(request, id):
    if request.method == "POST":
        data = dict(request.POST.items())
        data["invitee_1"] = request.user.id
        form = CalendarInviteForm(data)
        if form.is_valid():
            try:
                invitees = []
                for i in range(1, 5):
                    user_id = form.cleaned_data.get("invitee_{i}".format(i=i))
                    if user_id is not None and len(user_id) > 0:
                        invitees.append(User.objects.get(pk=user_id))
                send_calendar_invite(request, form.cleaned_data, invitees, "update")
                back = reverse_url(day_view) + "/" + timezones.as_iso_date(form.cleaned_data["date"])
                return redirect(back)
            except EmailingException, e:
                form.add_error(None, str(e))

    else:
        server_time, booking_data = get_booking_form_data(id)
        if booking_data is None:
            error = "Booking not found - has it already been deleted?"
            form = CalendarInviteForm(empty_permitted=True)
            form.is_valid()  # initializes cleaned_data
            form.add_error(None, error)
        else:
            created_by_id = booking_data["created_by_id"]
            booking_data["location"] = CalendarInviteForm.get_location(booking_data)
            booking_data["summary"] = CalendarInviteForm.get_summary(booking_data)
            booking_data["invitee_1"] = request.user.id
            try:
                court_booker = Player.objects.get(booking_system_id=created_by_id)
                if court_booker.user.id != request.user.id:
                    booking_data["invitee_2"] = court_booker.user.id
            except Player.DoesNotExist:
                pass
            form = CalendarInviteForm(initial=booking_data)

    add_formfield_attrs(form)
    context = {
        'form': form,
        'id': id,
        'back_url': reverse_url('booking') + "/{id}".format(**locals()),
    }
    return TemplateResponse(request, 'cal_invite.html', context)


@login_required
def agenda_view(request):
    start_date = request.GET.get("start_date")
    if start_date is None:
        start_date = datetime.date.today()
    else:
        start_date = timezones.parse_iso_date_to_naive(start_date)
    agenda_items = BookingSystemEvent.objects.filter(is_active=True, start_time__gte=start_date)

    name = request.GET.get("name")
    filter_created_by = False
    if name is None:
        name = request.user.get_full_name()
        filter_created_by = True

    name_clause = Q(name__icontains=name)
    name_clause |= Q(opponent__icontains=name)
    name_clause |= Q(description__icontains=name)
    if filter_created_by:
        myself = Player.get_player_for_user(request.user)
        if myself is not None:
            name_clause |= Q(created_by=myself)

    agenda_items = agenda_items.filter(name_clause)
    context = {'agenda_items': agenda_items, 'name': name, 'using_local_database': using_local_database()}
    return TemplateResponse(request, 'agenda.html', context)


@login_required
def notifier_view(request):
    max_filters = 7
    filter_formset_factory = create_notifier_filter_formset_factory(max_filters)
    success = False
    player = Player.get_player_for_user(request.user)
    events = EventFilter.objects.filter(player=player)
    initial = [{'player': player}] * max_filters
    if request.method == 'POST':
        eformset = filter_formset_factory(request.POST, queryset=events, initial=initial)
        if eformset.is_valid():
            with transaction.atomic():
                for form in eformset:
                    if form.has_changed():
                        if form.cleaned_data['player'] != player:
                            raise PermissionDenied()
                if eformset.has_changed():
                    eformset.save()
                    events = EventFilter.objects.filter(player=player)
                    eformset = filter_formset_factory(queryset=events, initial=initial)
                success = True
    else:
        eformset = filter_formset_factory(queryset=events, initial=initial)
    context = {
        'notify_formset':  eformset,
        'n_notifiers':     len(events),
        'form_saved':      success,
    }
    return TemplateResponse(request, 'notifier.html', context)


@login_required
def penalty_points_view(request):
    player = Player.get_player_for_user(request.user)
    if player is None:
        return HttpResponseNotFound()
    total_offences = BookingOffence.get_offences_for_player(player)
    context = {
        "player": player,
        "total_offences": total_offences,
        "total_points": BookingOffence.get_total_points_for_player(player, None, total_offences),
        "point_limit": BookingOffence.POINT_LIMIT
    }
    return TemplateResponse(request, 'penalty_points.html', context)


@method_decorator(login_required, name='dispatch')
class CondensationReportCreateView(CreateView):
    template_name = 'condensation_report_form.html'
    success_url = reverse_lazy("condensation_report")
    form_class = CondensationReportForm

    def form_valid(self, form):
        form.instance.reporter = self.request.user.player
        self.object = form.save()
        context = self.get_context_data(form=self.get_form())
        context["form_saved"] = True
        return self.render_to_response(context)
