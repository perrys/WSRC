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
import logging
import operator
import sys
import unittest

from django.core.mail import SafeMIMEMultipart, SafeMIMEText

from email.mime.application import MIMEApplication

LOGGER = logging.getLogger(__name__)

import wsrc.site.settings.settings as settings
from wsrc.utils import email_utils
from wsrc.utils.timezones import UK_TZINFO, as_iso_date

def get_audit_table_and_noshows(date):
    from .models import BookingSystemEvent, BookingSystemEventAuditEntry
    audit_table = BookingSystemEventAuditEntry.objects.filter(updated=date).order_by("updated")
    noshows = BookingSystemEvent.objects.filter(start_time__date=date, no_show=True)
    return audit_table, noshows

def booked_another_court(audit_data, cancelled_item):
    booked_courts = {}
    for item in audit_data:
        if item.booking == cancelled_item.booking:
            continue
        if item.update_type == "C" \
           and item.booking.created_by_user == cancelled_item.booking.created_by_user \
           and item.booking.start_time.date() == cancelled_item.booking.start_time.date():
            booked_courts[item.booking.pk] = item.booking
        elif item.update_type == "D":
            id = item.booking.pk
            if id in booked_courts:
                del booked_courts[id]
    rebooked = len(booked_courts) > 0
    if rebooked:
        LOGGER.info("entry filtered as another court booked: %s", cancelled_item.booking)
    return rebooked

def court_rebooked(audit_data, cancelled_item):
    last_item = None
    for item in audit_data:
        match = True
        for field in ["date", "start_minutes", "court"]:
            if getattr(item.booking, field) != getattr(cancelled_item.booking, field):
                match = False
                break
        if match:
            last_item = item
    assert(last_item is not None)
    if "D" == last_item.update_type:
        return False
    return True

def audit_filter(audit_data, item):
    from wsrc.site.courts.views import has_admin_permission
    if item.update_type != "D":
        return True
    if booked_another_court(audit_data, item):
        return True
    if item.updated_by.is_superuser:
        return True
    if has_admin_permission(item.updated_by, raise_exception=False):
        return True
    return False

def process_audit_table(audit_data, player_offence_map, error_list, filter=None):
    import wsrc.site.courts.models as court_models
    import wsrc.site.usermodel.models as user_models
    players = user_models.Player.objects.filter(user__is_active=True)
    user_id_map = dict([(p.user.pk, p) for p in players])
    for item in audit_data:
        if filter is not None and filter(item):
            continue
        start_time = item.booking.start_time
        creation_time = item.booking.created_time
        delta_t_hours = 0
        prebook_hours = (start_time - creation_time).total_seconds() / 3600.0
        cancellation_time = item.updated
        if cancellation_time is not None:
            delta_t_hours = (start_time - cancellation_time).total_seconds() / 3600.0
        player = user_id_map.get(item.booking.created_by_user.pk)
        if player is None:
            msg = "Player not active for booking {0}".format(item.booking)
            error_list.append({"msg": msg, "data": item})
            LOGGER.warning(msg)
            continue
        rebooked = court_rebooked(audit_data, item)
        points = court_models.BookingOffence.get_points(delta_t_hours, prebook_hours)
        if points == 0:
            continue
        offence = court_models.BookingOffence(
          player  = player,
          offence = "lc",
          entry_id = item.booking.pk,
          start_time = start_time,
          duration_mins = item.booking.duration_minutes,
          court = item.booking.court,
          name = item.booking.name,
          description = item.booking.description,
          owner = item.booking.created_by_user.get_full_name(),
          creation_time = creation_time,
          cancellation_time = cancellation_time,
          rebooked = rebooked,
          penalty_points = points
        )
        offence.save()
        player_offence_map.setdefault(player, []).append(offence)

def report_errors(date, errors):
    subject = "Booking Monitor Error"
    from_address = to_address = "webmaster@wokingsquashclub.org"
    text_body, html_body = email_utils.get_email_bodies("BookingMonitorErrors", {"errors": errors, "date": date})
    encoding = settings.DEFAULT_CHARSET
    msg_bodies = SafeMIMEMultipart(_subtype="alternative", encoding=encoding)
    msg_bodies.attach(SafeMIMEText(text_body, "plain", encoding))
    msg_bodies.attach(SafeMIMEText(html_body, "html", encoding))
    attachments = [msg_bodies]
    for error in errors:
        msg = MIMEApplication(json.dumps(error["data"], cls=DateTimeEncoder), "json")
        msg.add_header('Content-Disposition', 'attachment', filename='{id}.json'.format(id=error["data"]["entry_id"]))
        attachments.append(msg)

    email_utils.send_email(subject, None, None, from_address, [to_address], extra_attachments=attachments)

def report_offences(date, player, offences, total_offences):
    from wsrc.site.courts.models import BookingOffence
    subject = "Cancelled/Unused Courts - {name} - {date:%Y-%m-%d}".format(name=player.user.get_full_name(), date=date)
    from_address = "booking.monitor@wokingsquashclub.org"
    daily_total = reduce(lambda x,y: x + y.penalty_points, offences, 0)
    to_list = [player.user.email or None]
    cc_address = "booking.monitor@wokingsquashclub.org"
    context = {
      "date": date,
      "player": player,
      "offences": offences,
      "total_offences": total_offences,
      "total_points": BookingOffence.get_total_points_for_player(player, date, total_offences),
      "point_limit": BookingOffence.POINT_LIMIT
    }
    text_body, html_body = email_utils.get_email_bodies("BookingOffenceNotification", context)
    email_utils.send_email(subject, text_body, html_body, from_address, to_list, cc_list=[cc_address])

def process_date(date):
    from wsrc.site.courts.models import BookingOffence
    LOGGER.info("processing date %s", as_iso_date(date))

    (noshows, audit_table) = get_audit_table_and_noshows(date)

    filter = lambda(i): audit_filter(audit_table, i)

    midnight_today = datetime.datetime.combine(date, datetime.time(0, 0, tzinfo=UK_TZINFO))
    midnight_tomorrow = midnight_today + datetime.timedelta(days=1)
    existing_offences = BookingOffence.objects.filter(start_time__gte=midnight_today, start_time__lt=midnight_tomorrow)
    if existing_offences.count() > 0:
        LOGGER.warning("found %s offence(s) already present for %s, deleting", existing_offences.count(), as_iso_date(date))
        existing_offences.delete()

    player_offence_map = dict()
    errors = list()

    process_audit_table(audit_table, player_offence_map, errors, filter)
#    process_noshows(noshows, player_offence_map, errors)
    if len(errors) > 0:
        report_errors(date, errors)
    for player, offences in player_offence_map.items():
        total_offences = BookingOffence.get_offences_for_player(player, date)
        report_offences(date, player, offences, total_offences)


