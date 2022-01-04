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

"""Court forms"""

import datetime

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms.fields import BaseTemporalField
from django.forms.models import modelformset_factory
from django.utils import timezone

import wsrc.site.settings.settings as settings
from wsrc.site.courts.models import DayOfWeek, EventFilter, CondensationReport, BookingSystemEvent
from wsrc.site.usermodel.models import Player, Subscription
from wsrc.utils import timezones
from wsrc.utils.form_utils import make_readonly_widget, LabeledSelect, CachingModelMultipleChoiceField, \
    add_formfield_attrs

COURTS = [1, 2, 3]
START_TIME = 8 * 60 + 15
END_TIME = 22 * 60 + 15
RESOLUTION = 15
EMPTY_DUR = 3 * RESOLUTION
START_TIMES = [datetime.time(hour=t / 60, minute=t % 60) for t in range(START_TIME, END_TIME - RESOLUTION, RESOLUTION)]
ALL_TIMES = [datetime.time(hour=t / 60, minute=t % 60) for t in range(0, 24 * 60, RESOLUTION)]
DURATIONS = [datetime.timedelta(minutes=i) for i in range(15, END_TIME - START_TIME, 15)]


def using_local_database():
    return hasattr(settings, "BOOKING_SYSTEM_SETTINGS")


def get_opponent_names():
    names = [(kv[1], kv[1]) for kv in get_active_user_choices() if kv[0] is not None]
    return [("Solo", "[Solo Practice]"), ("Guest", "[Guest]"),  ("Coaching", "[Coaching]")] + names


def get_active_user_choices():
    subscriptions = Subscription.objects.filter(player__user__is_active=True, season__has_ended=False) \
        .order_by("player__user__first_name", "player__user__last_name")
    users = [s.player.user for s in subscriptions]
    return [(None, '')] + [(u.id, u.get_full_name()) for u in users]


def validate_15_minute_multiple(value):
    rem = value % 15
    if rem != 0:
        raise ValidationError("{value} is not a 15-minute multiple".format(**locals()))


def validate_quarter_hour(value):
    if value.second != 0 or value.microsecond != 0:
        raise ValidationError("{value} has less than minute resolution".format(**locals()))
    validate_15_minute_multiple(value.minute)


def validate_not_future(value):
    if value > timezone.now():
        raise ValidationError("{value} is in the future!".format(**locals()))


def validate_quarter_hour_duration(value):
    value = value.total_seconds()
    if (value % 60) != 0:
        raise ValidationError("{value} has less than minute resolution".format(**locals()))
    validate_15_minute_multiple(value / 60)


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
    opponent = forms.ChoiceField(choices=[(None, "")] + get_opponent_names(),
                                 widget=LabeledSelect(default_label="(please select)", disable_default=True,
                                                      attrs={'autofocus': True}),
                                 required=False)

    description = forms.CharField(required=False, widget=forms.TextInput)

    date = forms.DateField(input_formats=make_date_formats())
    start_time = forms.TimeField(label="Time", input_formats=['%H:%M'], validators=[validate_quarter_hour],
                                 widget=forms.Select(
                                     choices=[(t.strftime("%H:%M"), t.strftime("%H:%M")) for t in START_TIMES]))
    duration = HourAndMinuteDurationField(validators=[validate_quarter_hour_duration], input_formats=[None],
                                          widget=forms.Select(
                                              choices=[(timezones.duration_str(i), timezones.duration_str(i)) for i in
                                                       DURATIONS]))
    court = forms.ChoiceField(choices=[(i, str(i)) for i in COURTS])
    booking_type = forms.ChoiceField(choices=[("I", "Member"), ("E", "Club")])

    created_by = forms.CharField(max_length=80, label="Created By", widget=make_readonly_widget(), required=False)
    created_ts = forms.DateTimeField(label="Created At", input_formats=make_datetime_formats(),
                                     widget=make_readonly_widget(), required=False)
    timestamp = forms.DateTimeField(label="Last Updated", input_formats=make_datetime_formats(),
                                    widget=make_readonly_widget(), required=False)

    booking_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    created_by_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    token = forms.CharField(required=False, widget=forms.HiddenInput())
    no_show = forms.BooleanField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super(BookingForm, self).__init__(*args, **kwargs)
        self.is_retry = False

    def set_admin(self):
        attrs = self.fields["description"].widget.attrs
        if "autofocus" in attrs:
            del attrs["autofocus"]
        attrs = self.fields["name"].widget.attrs
        attrs["autofocus"] = "autofocus"

    def is_authorized(self, user):
        if not self.is_valid():
            return False

        if using_local_database():
            return BookingSystemEvent.is_writable(self.cleaned_data.get("created_by_id"), user)

        # Legacy system - check the booking user id matches
        player = Player.get_player_for_user(user)
        booking_user_id = None if player is None else player.booking_system_id
        return booking_user_id is not None and \
               booking_user_id == booking_form.cleaned_data.get("created_by_id")

    @staticmethod
    def transform_to_booking_system_event(cleaned_data):
        slot = dict()
        start_time = cleaned_data["start_time"].replace(tzinfo=timezones.UK_TZINFO)
        slot["start_time"] = datetime.datetime.combine(cleaned_data["date"], start_time)
        slot["end_time"] = slot["start_time"] + cleaned_data["duration"]
        mapping = {"court": None, "name": None, "opponent": None, "description": None, "event_type": "booking_type",
                   "created_time": "created_ts"}
        for k, v in mapping.items():
            if v is None: v = k
            value = cleaned_data.get(v)
            slot[k] = value
        return BookingSystemEvent(**slot)

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
    def transform_booking_model(entry):
        slot = dict()
        mapping = {"name": None, "opponent": None, "description": None, "date": None, "duration": None, "court": None,
                   "booking_type": "event_type", "booking_id": "pk",
                   "no_show": None, "token": None}
        for k, v in mapping.items():
            value = getattr(entry, v if v is not None else k)
            slot[k] = value
        mapping = {"start_time": lambda (s): s.start_time.astimezone(timezones.UK_TZINFO).time(),
                   "created_by": lambda (s): s.created_by_user.get_full_name() if s.created_by_user is not None else "",
                   "created_by_id": lambda (s): s.created_by_user.pk if s.created_by_user is not None else None,
                   "created_ts": lambda (s): s.created_time.astimezone(timezones.UK_TZINFO)
                       if s.created_time is not None else "",
                   "timestamp": lambda (s): s.last_updated.astimezone(timezones.UK_TZINFO),
                   }
        for k, v in mapping.items():
            value = v(entry)
            slot[k] = value

        def format_date1(k, fmts):
            slot[k] = slot[k].strftime(fmts[0])

        format_date1("start_time", ["%H:%M"])
        format_date1("date", make_date_formats())
        if entry.created_time is not None:
            format_date1("created_ts", make_datetime_formats())
        format_date1("timestamp", make_datetime_formats())
        dur = slot["duration"]
        if not isinstance(dur, datetime.timedelta):
            dur = datetime.timedelta(minutes=dur)
        slot["duration"] = timezones.duration_str(dur)
        return slot

    @staticmethod
    def empty_form(error=None):
        booking_form = BookingForm(empty_permitted=True, data={})
        booking_form.is_valid()  # initializes cleaned_data
        if error is not None:
            booking_form.add_error(None, error)
        return booking_form


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
    invitee_1 = forms.ChoiceField(choices=get_active_user_choices(),
                                  widget=LabeledSelect(attrs={'disabled': 'disabled', 'class': 'readonly'}))
    invitee_2 = forms.ChoiceField(choices=get_active_user_choices(),
                                  widget=LabeledSelect(attrs={'autofocus': 'autofocus'}))
    invitee_3 = forms.ChoiceField(choices=get_active_user_choices(), widget=LabeledSelect, required=False)
    invitee_4 = forms.ChoiceField(choices=get_active_user_choices(), widget=LabeledSelect, required=False)

    @staticmethod
    def get_location(booking_data):
        return "Court {court}, Woking Squash Club, Horsell Moor, Woking GU21 4NR".format(**booking_data)

    @staticmethod
    def get_summary(booking_data):
        return u"WSRC Court Booking - {name}".format(**booking_data)


class NotifierForm(forms.ModelForm):
    days = CachingModelMultipleChoiceField(DayOfWeek.objects.all(), widget=forms.CheckboxSelectMultiple())

    class Meta:
        model = EventFilter
        fields = ["earliest", "latest", "notice_period_minutes", "days", "player"]

    def __init__(self, *args, **kwargs):
        super(NotifierForm, self).__init__(*args, **kwargs)
        add_formfield_attrs(self)


def create_notifier_filter_formset_factory(max_number):
    time_choices = [
        ("", "Please Select"),
        ("08:00:00", "8am"),
        ("10:00:00", "10am"),
        ("12:00:00", "12pm"),
        ("14:00:00", "2pm"),
        ("16:00:00", "4pm"),
        ("17:00:00", "5pm"),
        ("18:00:00", "6pm"),
        ("18:30:00", "6:30pm"),
        ("19:00:00", "7pm"),
        ("19:30:00", "7:30pm"),
        ("20:00:00", "8pm"),
        ("21:00:00", "9pm"),
        ("22:00:00", "10pm"),
    ]
    notice_period_choices = [
        ("", "Please Select"),
        (30, "30 minutes"),
        (60, "1 hour"),
        (120, "2 hours"),
        (180, "3 hours"),
        (240, "4 hours"),
        (300, "5 hours"),
        (360, "6 hours"),
        (720, "12 hours"),
        (1440, "1 day"),
    ]
    return modelformset_factory(
        EventFilter,
        form=NotifierForm,
        can_delete=True,
        extra=max_number,
        max_num=max_number,
        widgets={
            "earliest": forms.Select(choices=time_choices, attrs={"data-inline": 1}),
            "latest": forms.Select(choices=time_choices, attrs={"data-inline": 1}),
            "notice_period_minutes": forms.Select(choices=notice_period_choices, attrs={"data-inline": 1}),
            "days": forms.CheckboxSelectMultiple(),
            "player": forms.HiddenInput(),
        }
    )


class SplitDateTimeSelectorWidget(forms.SplitDateTimeWidget):
    """
    A Widget that splits datetime input into one <input type="text"> and one select dropdown.
    """

    def __init__(self, time_choices, attrs=None, date_format="%-d/%-m/%Y"):
        if attrs is None:
            attrs = {"class": "date-input"}
        widgets = (
            forms.DateInput(attrs=attrs, format=date_format),
            forms.Select(attrs=attrs, choices=time_choices),
        )
        super(forms.SplitDateTimeWidget, self).__init__(widgets, attrs)


class CondensationReportForm(forms.ModelForm):
    time = forms.SplitDateTimeField(
        widget=SplitDateTimeSelectorWidget(
            time_choices=[(t.strftime("%H:%M:%S"), t.strftime("%-I:%M %P")) for t in ALL_TIMES]
        ),
        validators=[validate_quarter_hour, validate_not_future],
        label="Observation Time"
    )

    def __init__(self, *args, **kwargs):
        if "data" not in kwargs:
            obj = CondensationReport()
            kwargs["initial"]["time"] = obj.time
        super(CondensationReportForm, self).__init__(*args, **kwargs)
        add_formfield_attrs(self)

    class Meta:
        model = CondensationReport
        fields = ["reporter", "time", "location", "comment"]
        widgets = {
            "reporter": forms.HiddenInput,
            "location": forms.CheckboxSelectMultiple
        }
