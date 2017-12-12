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

"Utilities for determining the activity of members of the club"

import collections
import datetime
import StringIO
import xlsxwriter

from django.db.models import Q

from wsrc.site.competitions.models import Match
from wsrc.site.courts.models import BookingSystemEvent
from wsrc.site.usermodel.models import Subscription, DoorEntryCard, DoorCardEvent
from wsrc.utils.timezones import UK_TZINFO

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SLOTS_PER_HOUR = 4


class ActivityReport(object):
    "Report on the activity of subscribed members between two dates"
    def __init__(self, start_date, end_date, subs_filter=\
                 Q(player__user__is_active=True) &\
                 Q(season__has_ended=False) &\
                 ~Q(subscription_type__short_code="junior") &\
                 ~Q(subscription_type__short_code="non_playing")\
    ):
        "Initialize report with given dates and filters"
        midnight = datetime.time(0, tzinfo=UK_TZINFO)
        self.start_date = datetime.datetime.combine(start_date, midnight)
        self.end_date = datetime.datetime.combine(end_date, midnight)
        self.subscriptions = Subscription.objects.select_related("player__user", "subscription_type", "season")\
                                                 .filter(subs_filter)
        self.matches = Match.objects.select_related("team1__player1__user", "team2__player1__user",
                                                    "team1__player2__user", "team2__player2__user",
                                                    "competition__group")\
                                    .filter(last_updated__gte=self.start_date,\
                                            last_updated__lt=self.end_date)
        self.bookings = BookingSystemEvent.objects\
                                          .select_related("created_by")\
                                          .filter(start_time__gte=self.start_date, start_time__lt=self.end_date)


    @staticmethod
    def _get_or_add_set(results, key, factory=lambda: set()):
        result = results.get(key)
        if result is None:
            result = results[key] = factory()
        return result

    def get_doorcard_events(self):
        dce_qs = DoorCardEvent.objects\
                              .filter(event="Granted",\
                                      received_time__gte=self.start_date,\
                                      received_time__lt=self.end_date)\
                              .select_related("card__player__user")
        
        results = dict()
        for dce in dce_qs:
            card = dce.card
            if card is not None and card.player is not None:
                player_list = self._get_or_add_set(results, card.player.pk, lambda: list())
                if len(player_list) > 0:
                    # ignore repeat entries by the same card
                    if (dce.timestamp - player_list[-1].timestamp).total_seconds() < (2 * 60 * 60):
                        continue
                player_list.append(dce)
        return results


    def get_courts_booked(self):
        results = dict()
        for booking in self.bookings:
            if booking.created_by is not None:
                player_set = self._get_or_add_set(results, booking.created_by.pk)
                player_set.add(booking)
        return results

    def get_matches_played(self):
        results = dict()
        for match in self.matches:
            players = match.team1.get_players()
            players.extend(match.team2.get_players())
            for player in players:
                player_set = self._get_or_add_set(results, player.pk)
                player_set.add(match)
        return results

    def get_court_usage(self):
        class Court:
            def __init__(self, court):
                self.court = court
                self.slots = [False] * (SLOTS_PER_HOUR * 24)
            def slot(self, start, end):
                slot = start.hour * SLOTS_PER_HOUR + (start.minute * SLOTS_PER_HOUR / 60)
                while start < end:
                    self.slots[slot] = True
                    start += datetime.timedelta(minutes=60/SLOTS_PER_HOUR)
                    slot += 1
        class Day:
            def __init__(self, date):
                self.date = date
                self.courts = [Court(idx) for idx in range(1,4)]
            def slot(self, booking):
                court = self.courts[booking.court-1]
                court.slot(booking.start_time, booking.end_time)

        def collate_bookings(bookings):
            dates = dict()
            for bslot in bookings:
                date = bslot.start_time.date()
                day = self._get_or_add_set(dates, date, lambda: Day(date))
                day.slot(bslot)
            return dates.values()

        def day_of_week_reduce(date_summaries):
            class DayAvg:
                def __init__(self):
                    self.count = 0
                    self.slots = [0.0 for jdx in range(0, (4*24))]
                def process(self):
                    return [self.count > 0 and (slot / self.count) or 0.0 for slot in self.slots]
            day_avg = [DayAvg() for i in range(0, 7)]
            for day in date_summaries:
                avg = day_avg[day.date.weekday()]
                for idx in range(0, 3):
                    court = day.courts[idx]
                    avg.count += 1
                    for (jdx,slot) in enumerate(court.slots):
                        if slot:
                            avg.slots[jdx] += 1
            return [s.process() for s in day_avg]

        date_summaries = collate_bookings(self.bookings)
        day_averages = day_of_week_reduce(date_summaries)
        print len(day_averages)
        result_t = collections.namedtuple("CourtUsage", ["time"] + WEEKDAYS)
        results = []
        for idx in range(SLOTS_PER_HOUR*7, SLOTS_PER_HOUR*23):
            time = "{hr:02d}:{min:02d}".format(hr=idx/SLOTS_PER_HOUR, min=15*(idx%SLOTS_PER_HOUR))
            avgs = [day_averages[dow][idx] for dow, day in enumerate(WEEKDAYS)]
            results.append(result_t._make([time] + avgs))
        return results

    def get_report_data(self):
        
        matches = self.get_matches_played()
        bookings = self.get_courts_booked()
        door_events = self.get_doorcard_events()
        players = []
        player_summary_type = collections.namedtuple("PlayerData",
                                                     ["sub", "player", "n_matches", "n_bookings",
                                                      "n_visits", "activity"])

        for sub in self.subscriptions:
            player = sub.player
            p_matches = matches.get(player.pk) or []
            p_bookings = bookings.get(player.pk) or []
            p_visits = door_events.get(player.pk) or []
            p_sum = player_summary_type(sub, player,
                                        len(p_matches), len(p_bookings), len(p_visits),
                                        len(p_matches) + len(p_bookings))
            players.append(p_sum)
        result_type = collections.namedtuple("ReportData", ['matches', 'bookings', 'door_events', 'players'])
        results = result_type(matches, bookings, door_events, players)
        return results

    def create_report(self):
        data = self.get_report_data()
        output = StringIO.StringIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'remove_timezone': True})
        header_format = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'bold': False,  'bottom': 1, 'bg_color': '#AEB6BF'})
        alt_color_fmt = {'bg_color': '#EBEDEF'}
        alt_row_format = workbook.add_format(alt_color_fmt)
        formats = {
            "date": {'num_format': 'd mmm yyyy'},
            "datetime": {'num_format': 'd mmm yyyy HH:MM'},
            "percent": {'num_format': '0.0%'},
        }
        cell_formats = {}
        for key, val in formats.iteritems():
            cell_formats[key] = workbook.add_format(val)
            fmt = val.copy()
            fmt.update(alt_color_fmt)
            cell_formats[key + "_alt"] = workbook.add_format(fmt)

        def getitem(record, name):
            for tok in name.split("."):
                item = record = getattr(record, tok)
                if hasattr(item, "__call__"):
                    item = record = item()
            return item
        
        def add_worksheet(name, data, fields, transform_row=None):
            worksheet = workbook.add_worksheet(name)
            for jdx, field in enumerate(fields):
                worksheet.set_column(jdx, jdx, field.width)
                worksheet.write(0, jdx, field.name, header_format)
            worksheet.freeze_panes(1, 0)
            for idx, row in enumerate(data):
                idx += 1
                if transform_row:
                    row = transform_row(row)
                for jdx, field in enumerate(fields):
                    if (idx & 1) == 0:
                        fmt = alt_row_format if field.fmt is None else cell_formats[field.fmt + "_alt"]
                    else:
                        fmt = None if field.fmt is None else cell_formats[field.fmt]
                    worksheet.write(idx, jdx, getitem(row, field.path), fmt)
            worksheet.autofilter(0, 0, len(data)+1, len(fields)-1)
            return worksheet

        col_t = collections.namedtuple("Col", ["name", "path", "fmt", "width"])
        add_worksheet("Activity Summary", data.players,
                      [col_t("Name", "player.get_ordered_name", None, 25),
                       col_t("Subscription", "sub.subscription_type.name", None, 15),
                       col_t("Joined", "player.user.date_joined", "date", 15),
                       col_t("# Matches", "n_matches", None, 12),
                       col_t("# Bookings", "n_bookings", None, 12),
                       col_t("# Visits", "n_visits", None, 12),
                       col_t("Activity", "activity", None, 12),
                      ])
        add_worksheet("Matches", self.matches,
                      [col_t("Competition", "competition.group.__unicode__", None, 35),
                       col_t("Name", "competition.name", None, 15),
                       col_t("Time", "last_updated", "datetime", 20),
                       col_t("Match", "get_teams_display", None, 40),
                       col_t("Score", "get_scores_display", None, 25),
                      ])
        cudata = self.get_court_usage()
        cuws = add_worksheet("Court Usage", cudata,
                             [col_t("Time", "time", None, 10)] +\
                             [col_t(dow, dow, "percent", 10) for dow in WEEKDAYS])

        def add_chart(col_range, insert_cell):
            chart = workbook.add_chart({'type': 'column'})
            chart.set_size({'width': 720})
            chart.set_y_axis({"max": 1, 'num_format': '0%'})
            for dow in col_range:
                chart.add_series({
                    'values': [cuws.name, 1, dow, len(cudata), dow],
                    'categories': [cuws.name, 1, 0, len(cudata), 0],
                    'name': [cuws.name, 0, dow]})
            cuws.insert_chart(insert_cell, chart)
        add_chart(range(1,6), "J2")
        add_chart(range(6,8), "J17")
        workbook.close()
        return output.getvalue()
