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
import functools
import operator
from django.utils import timezone

from .models import BookingSystemEvent
from wsrc.site.settings import settings

def add_free_slots(court, booked_slots, booking_date_midnight, now, ignore_cutoff=False):
    
    RESOLUTION_MINS = settings.BOOKING_SYSTEM_RESOLUTION_MINS

    COVID_LOCKDOWN_DAY = timezone.make_aware(datetime.datetime(2020, 3, 21))
    COVID_FREEDOM_DAY = timezone.make_aware(datetime.datetime(2021, 07, 19))
    if booking_date_midnight >= COVID_LOCKDOWN_DAY and booking_date_midnight < COVID_FREEDOM_DAY:
        STAGGER = 4
    else:
        STAGGER = settings.BOOKING_SYSTEM_STAGGER_SET
    DEFAULT_DURATION = STAGGER * RESOLUTION_MINS

    STARTS_ENDS = settings.BOOKING_SYSTEM_STARTS_ENDS
    CUTOFF_PERIOD = datetime.timedelta(days=settings.BOOKING_SYSTEM_CUTOFF_DAYS)

    booked_slots.sort(key=operator.itemgetter("start_mins"))
    room_offset_mins = (court-1) * RESOLUTION_MINS;
    start_mins = STARTS_ENDS[0] + room_offset_mins
    end_mins = STARTS_ENDS[1] + room_offset_mins - RESOLUTION_MINS
    mins_to_slot = dict([(c.start_minutes, c) for c in booked_slots])
    nbookings = len(booked_slots)
    idx = 0
    cutoff_point = now + CUTOFF_PERIOD

    iter_mins = 7*60 # sometimes courts are reserved by admin earlier than they can be booked.
    while iter_mins < end_mins:
        booked_slot = mins_to_slot.get(iter_mins)
        if booked_slot is not None:
            iter_mins += booked_slot.duration_minutes
            continue
        if iter_mins < start_mins:
            iter_mins += RESOLUTION_MINS
            continue
        next_start = end_mins
        while idx < nbookings:
            booked_slot = booked_slots[idx]
            if booked_slot.start_minutes > iter_mins:
                next_start = booked_slot.start_minutes
                break
            idx += 1
        # fill to next start (or end)..
        
        while iter_mins < next_start:
            duration_mins = next_start - iter_mins
            if duration_mins > DEFAULT_DURATION:
                # try to align with the normal slots for this court
                remainder = (iter_mins - start_mins) % DEFAULT_DURATION
                duration_mins = DEFAULT_DURATION - remainder;
            slot_dt = booking_date_midnight + datetime.timedelta(minutes=iter_mins)
            slot_end_dt = slot_dt + datetime.timedelta(minutes=duration_mins)
            booking = {
                "start_time": slot_dt.strftime("%H:%M"),
                "start_mins": iter_mins,
                "duration_mins": duration_mins,
            }
            if slot_end_dt > now and (ignore_cutoff or slot_dt < cutoff_point):
                booking["token"] = BookingSystemEvent.generate_hmac_token(slot_dt, court);
            booked_slots.append(booking)
            iter_mins += duration_mins
    return booked_slots
