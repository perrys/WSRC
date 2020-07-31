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

import csv
import datetime
from operator import itemgetter

from django import forms
from django.contrib import admin
from django.db import models, transaction
from django.shortcuts import redirect
from django.utils import timezone

from wsrc.site.courts.models import BookingOffence, EventFilter, BookingSystemEvent, ClimateMeasurement, \
    CondensationLocation, CondensationReport, BookingSystemEventAuditEntry
from wsrc.site.usermodel.models import Player
from wsrc.utils import timezones
from wsrc.utils.admin_utils import CSVModelAdmin
from wsrc.utils.form_utils import PrefetchRelatedQuerysetMixin, get_related_field_limited_queryset
from wsrc.utils.upload_utils import upload_generator


class OffendersListFilter(admin.SimpleListFilter):
    title = "offender"
    parameter_name = "offender"

    def lookups(self, request, model_admin):
        players = dict()
        for offence in BookingOffence.objects.all().select_related("player__user"):
            players[offence.player.id] = offence.player
        players = players.values()
        players.sort(cmp=lambda x, y: cmp(x.user.get_full_name(), y.user.get_full_name()))
        return [(item.user.username, item.user.get_full_name()) for item in players]

    def queryset(self, request, queryset):
        val = self.value()
        if val is not None:
            queryset = queryset.filter(player__user__username=val)
        return queryset


def set_inactive(modeladmin, request, queryset):
    queryset.update(is_active=False)


def set_active(modeladmin, request, queryset):
    queryset.update(is_active=True)


class BookingOffenceAdmin(CSVModelAdmin):
    list_display = ("player", "entry_id", "offence", "start_time", "creation_time", \
                    "cancellation_time", "rebooked", "penalty_points", "is_active", "comment")
    list_editable = ("penalty_points", "is_active", "comment")
    list_filter = (OffendersListFilter,)
    date_hierarchy = "start_time"
    actions = (set_inactive, set_active)
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 30, 'rows': 1})},
        models.IntegerField: {'widget': forms.NumberInput(attrs={'style': 'width: 3em;'})},
    }

    def get_queryset(self, request):
        queryset = super(BookingOffenceAdmin, self).get_queryset(request)
        queryset = queryset.select_related('player__user')
        return queryset


class UserModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return Player.make_ordered_name(obj.last_name, obj.first_name)


class NotifierEventAdmin(PrefetchRelatedQuerysetMixin, CSVModelAdmin):
    list_display = ("player", "earliest", "latest", "get_day_list", "notice_period_minutes")
    list_select_related = ('player__user',)
    prefetch_related_fields = ('days',)

    def get_day_list(self, obj):
        return ",".join([str(d) for d in obj.days.all()])

    get_day_list.short_description = "Days"


class BookingAuditInline(admin.TabularInline):
    model = BookingSystemEventAuditEntry
    can_delete = False
    readonly_fields = ("update_type", "name", "description", "event_type", "updated", "updated_by")


class BookingForm(forms.ModelForm):
    queryset = get_related_field_limited_queryset(BookingSystemEventAuditEntry.updated_by.field) \
        .order_by("last_name", "first_name")
    created_by_user = UserModelChoiceField(queryset)
    last_updated_by = UserModelChoiceField(queryset)

    class Meta:
        model = BookingSystemEvent
        exclude = ["created_by"]


class BookingAdmin(CSVModelAdmin):
    form = BookingForm
    search_fields = ('name', 'description')
    list_display = (
        "name", "is_active", "start_time", "end_time", "court", "event_type", "description", "created_by_user",
        "created_time", "last_updated_by", "last_updated", "used")
    date_hierarchy = "start_time"
    list_filter = ("is_active", "court", "event_type", "no_show")
    list_select_related = ("created_by__user",)
    save_as = True
    inlines = (BookingAuditInline,)

    def get_queryset(self, request):
        qs = super(BookingAdmin, self).get_queryset(request)
        qs = qs.select_related("last_updated_by", "created_by_user", "no_show_reporter")
        return qs

    def used(self, obj):
        if obj.start_time > timezone.now() + datetime.timedelta(minutes=15):
            return None
        return not obj.no_show

    used.short_description = "Showed up"
    used.boolean = True


class ClimateMeasurementListUploadForm(forms.Form):
    upload_file = forms.FileField(required=False, label="Click to select HT160 .txt file. ",
                                  widget=forms.widgets.ClearableFileInput(attrs={'accept': '.txt'}))


class ClimateMeasurementAdmin(CSVModelAdmin):
    list_display = ("location", "time", "temperature_display", "dew_point_display", "relative_humidity_display",
                    "pressure_display")
    date_hierarchy = "time"
    list_filter = ("location",)
    list_per_page = 1000

    def get_urls(self):
        from django.conf.urls import url
        urls = super(ClimateMeasurementAdmin, self).get_urls()
        my_urls = [url(r"^upload_ht160_data/$", self.admin_site.admin_view(self.upload_view),
                       name='upload_ht160_data')]
        return my_urls + urls

    urls = property(get_urls)

    def changelist_view(self, *args, **kwargs):
        view = super(ClimateMeasurementAdmin, self).changelist_view(*args, **kwargs)
        if hasattr(view, "context_data"):
            view.context_data['upload_form'] = ClimateMeasurementListUploadForm
        return view

    @classmethod
    def parse_data(cls, fh):
        reader = csv.reader(fh)
        params = dict()
        data = []
        fieldnames = None
        for line in reader:
            if len(line) == 2:
                params[line[0]] = line[1]
            elif len(line) > 2:
                if fieldnames is None:
                    fieldnames = [l.upper() for l in line]
                else:
                    data.append(dict(zip(fieldnames, line)))
        return params, data

    @classmethod
    def save(cls, params, data):
        def convert_time(record):
            ts = record["TIME"]
            ts = datetime.datetime.strptime(ts, "%m-%d-%y %H:%M:%S")
            ts = ts.replace(tzinfo=timezones.UK_TZINFO)
            return ts

        FIELD_MAPPING = {
            "time": convert_time,
            "temperature": itemgetter("TEMP()"),
            "relative_humidity": itemgetter("HUMI(%RH)"),
            "dew_point": itemgetter("DP()"),
            "temperature_error": lambda x: 1.0,
            "relative_humidity_error": lambda x: 3.0,
            "dew_point_error": lambda x: 1.0,
        }
        with transaction.atomic():
            for row in data:
                kwargs = dict([(field, f(row)) for field, f in FIELD_MAPPING.items()])
                model = ClimateMeasurement(location=params["Test Name"], **kwargs)
                model.save()

    def upload_view(self, request):
        if request.method == 'POST':
            form = ClimateMeasurementListUploadForm(request.POST, request.FILES)
            if form.is_valid():
                codec = "utf-16le"
                line_generator = upload_generator(request.FILES['upload_file'], codec, "ascii")
                params, data = self.parse_data(line_generator)
                self.save(params, data)
            return redirect("admin:courts_climatemeasurement_changelist")


class CondensationLocationAdmin(admin.ModelAdmin):
    list_display = ("name",)


class CondensationReportForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(CondensationReportForm, self).__init__(*args, **kwargs)
        member_queryset = get_related_field_limited_queryset(CondensationReport.reporter.field) \
            .filter(user__is_active=True).select_related("user")
        self.fields['reporter'].queryset = member_queryset


class CondensationReportAdmin(CSVModelAdmin):
    form = CondensationReportForm
    list_display = ("time", "get_locations_display", "reporter", "comment")
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 100, 'rows': 5})},
        models.ManyToManyField: {'widget': forms.CheckboxSelectMultiple},
    }
    list_select_related = ('reporter__user',)

    def get_queryset(self, request):
        queryset = super(CondensationReportAdmin, self).get_queryset(request)
        queryset = queryset.select_related('reporter__user')
        return queryset


admin.site.register(BookingSystemEvent, BookingAdmin)
admin.site.register(BookingOffence, BookingOffenceAdmin)
admin.site.register(EventFilter, NotifierEventAdmin)
admin.site.register(ClimateMeasurement, ClimateMeasurementAdmin)
admin.site.register(CondensationLocation, CondensationLocationAdmin)
admin.site.register(CondensationReport, CondensationReportAdmin)
