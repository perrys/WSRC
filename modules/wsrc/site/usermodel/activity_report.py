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
import colorsys
import datetime
import os.path
import StringIO
import xlsxwriter

from django.db.models import Q
from django.contrib.staticfiles import finders

from wsrc.site.competitions.models import Match, Competition
from wsrc.site.courts.models import BookingSystemEvent, BookingOffence
from wsrc.site.usermodel.models import Subscription, DoorEntryCard, DoorCardEvent
from wsrc.utils.timezones import UK_TZINFO

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SLOTS_PER_HOUR = 4
COL_T = collections.namedtuple("Col", ["name", "path", "fmt", "width"])
        


class ActivityReport(object):
    "Report on the activity of subscribed members between two dates"
    def __init__(self, start_date, end_date, subs_filter=\
                 Q(player__user__is_active=True) &\
                 Q(season__has_ended=False) &\
                 ~Q(subscription_type__short_code="junior")\
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
                                            last_updated__lt=self.end_date,\
                                            team1_id__isnull=False, team2_id__isnull=False,\
                                            team1_score1__isnull=False, team2_score1__isnull=False)
        self.bookings = BookingSystemEvent.objects\
                                          .select_related("created_by")\
                                          .filter(is_active=True, start_time__gte=self.start_date, start_time__lt=self.end_date)\
.exclude(name__iexact="Blocked")
        self.offences = BookingOffence.objects.filter(start_time__gte=self.start_date, start_time__lt=self.end_date)
        self.competitions = Competition.objects.select_related("group")\
                                               .prefetch_related("entrant_set")\
                                               .filter(group__end_date__gte=self.start_date)


    @staticmethod
    def _get_or_add_set(results, key, factory=lambda: set()):
        result = results.get(key)
        if result is None:
            result = results[key] = factory()
        return result

    @staticmethod
    def getitem(record, name):
        for tok in name.split("."):
            item = record = getattr(record, tok)
            if hasattr(item, "__call__"):
                item = record = item()
        return item

    @staticmethod
    def write_data_to_sheet(worksheet, data, fields, cell_formats, row_idx, col_idx, alt_row_format=None, autofilter=False, totals=None, width_in_cells=False):
        merged_cells = 0
        rows = 0
        for jdx, field in enumerate(fields):
            jdx += col_idx + merged_cells
            if not width_in_cells:
                worksheet.set_column(jdx, jdx, field.width)
            if width_in_cells and field.width > 1:
                worksheet.merge_range(row_idx, jdx, row_idx, jdx+field.width-1, field.name, cell_formats["header"])
                merged_cells += field.width - 1
            else:
                worksheet.write(row_idx, jdx, field.name, cell_formats["header"])
        rows += 1
        if totals is not None:
            totals = dict([(jdx, 0) for jdx in totals])
        for idx, row in enumerate(data):
            idx += row_idx + 1
            merged_cells = 0
            rows += 1
            for jdx, field in enumerate(fields):
                field_idx = jdx
                jdx += col_idx + merged_cells
                if (idx & 1) == 0 and alt_row_format is not None:
                    fmt = alt_row_format if field.fmt is None else cell_formats[field.fmt + "_alt"]
                else:
                    fmt = None if field.fmt is None else cell_formats[field.fmt]
                val = ActivityReport.getitem(row, field.path)
                if width_in_cells and field.width > 1:
                    worksheet.merge_range(idx, jdx, idx, jdx+field.width-1, val, fmt)
                    merged_cells += field.width - 1
                else:
                    worksheet.write(idx, jdx, val, fmt)
                if totals is not None and field_idx in totals:
                    try:
                        totals[field_idx] += int(val)
                    except ValueError:
                        pass
        if autofilter:
            worksheet.autofilter(row_idx, col_idx, row_idx+len(data)+1, col_idx+len(fields)-1)
        if totals is not None:
            merged_cells = 0
            idx = row_idx+len(data)+1
            rows += 1
            for jdx, field in enumerate(fields):
                total = totals.get(jdx)
                if jdx is None:
                    continue
                jdx += col_idx + merged_cells
                if width_in_cells and field.width > 1:
                    worksheet.merge_range(idx, jdx, idx, jdx+field.width-1, total, cell_formats["total"])
                    merged_cells += field.width - 1
                else:
                    worksheet.write(idx, jdx, total, cell_formats["total"])
        return rows

    @staticmethod
    def write_heatmap(workbook, worksheet, data, cell_formats, row_headers, col_headers, row_idx, col_idx):
        low_color = (0.8, 0.01, 1.0)
        high_color = (0.01, 1.0, 1.0)
        def make_rgb(val):
            hsv = [low_color[i] + val * (high_color[i] - low_color[i]) for i in range(0,3)]
            rgb = colorsys.hsv_to_rgb(*hsv)
            return "#{0:02X}{1:02X}{2:02X}".format(*[int(val*255) for val in rgb])
        for jdx, header in enumerate(col_headers):
            jdx = jdx * 2 + col_idx + 1
            worksheet.merge_range(row_idx, jdx, row_idx, jdx+1, header, cell_formats["header"])
        for idx, header in enumerate(row_headers):
            idx += row_idx+1
            worksheet.write(idx, col_idx, header, cell_formats["header"])
            worksheet.set_row(idx, 20)
        for idx, row in enumerate(data):
            idx += row_idx+1
            for jdx, val in enumerate(row):
                jdx = jdx * 2 + col_idx + 1
                fmt = {'num_format': '0.%', 'bg_color': make_rgb(val)}
                print fmt
                fmt = workbook.add_format(fmt)
                worksheet.merge_range(idx, jdx, idx, jdx+1, val, fmt)
        return row_idx + 1 + len(data)
    
    def get_doorcard_events(self):
        dce_qs = DoorCardEvent.objects\
                              .filter(event="Granted",\
                                      received_time__gte=self.start_date,\
                                      received_time__lt=self.end_date)\
                              .prefetch_related("card__doorcardlease_set__player__user")
        
        results = dict()
        for dce in dce_qs:
            card = dce.card
            if card is not None:
                current_lease = card.get_current_ownership_data()
                if current_lease is None:
                    continue
                player_list = self._get_or_add_set(results, current_lease.player.pk, lambda: list())
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

    def get_match_summary(self):
        results = dict()
        for match in self.matches:
            comp = self._get_or_add_set(results, match.competition)
            comp.add(match)
        results_t = collections.namedtuple("CompData", ["group", "comp", "n_matches"])
        results = [results_t(comp.group, comp, len(c_set)) for comp, c_set in results.iteritems()]
        results.sort(key=lambda x: x.comp.ordering)
        results.sort(key=lambda x: x.group.end_date)
        return results, [COL_T("Group", "group.name", None, 9),
                         COL_T("Name", "comp.name", None, 4),
                         COL_T("Matches", "n_matches", None, 2)]
        
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
        result_t = collections.namedtuple("CourtUsage", ["time"] + WEEKDAYS)
        results = []
        for idx in range(SLOTS_PER_HOUR*7, SLOTS_PER_HOUR*23):
            time = "{hr:02d}:{min:02d}".format(hr=idx/SLOTS_PER_HOUR, min=15*(idx%SLOTS_PER_HOUR))
            avgs = [day_averages[dow][idx] for dow, day in enumerate(WEEKDAYS)]
            results.append(result_t._make([time] + avgs))
        return results

    def bucket_court_usage(self, data, bin_width):
        results = []
        bin_idx = 0
        sums = [0] * 7
        first_time = ""
        result_t = collections.namedtuple("CourtUsage", ["time"] + WEEKDAYS)
        for row_idx, row in enumerate(data):
            if bin_idx == 0:
                first_time = row[0]
            bin_idx += 1
            for dow, val in enumerate(row[1:]):
                sums[dow] += val
            if bin_idx == bin_width or row_idx == len(data)-1:
                time = "{first}-".format(first=first_time)
                results.append(result_t(time, *[float(val)/bin_width for val in sums]))
                bin_idx = 0
                sums = [0] * 7
        return results
                
    def get_court_usage_summary(self):
        result_t = collections.namedtuple("CourtSummary", ["booking_type", "slots", "fraction", "peak_slots", "peak_fraction"])
        results = dict([(typ, [0,0]) for typ in ("Club Night", "Teams", "Junior Coaching", "Members", "Other")])
        total = 0
        total_peak = 0
        for booking in self.bookings:
            duration_mins = int((booking.end_time - booking.start_time).total_seconds() / 60)
            total += duration_mins
            is_peak = booking.start_time.time().hour >= 17 and booking.start_time.time().hour <= 20 and booking.start_time.date().weekday() <= 4
            if is_peak:
                total_peak += duration_mins
            name = booking.name.lower().strip()
            def add(key):
                totals = results[key]
                totals[0] += duration_mins
                if is_peak:
                    totals[1] += duration_mins
            if name == "club night":
                add("Club Night")
            elif (" vs " in name or " vs. " in name) and\
                 ("mens" in name or "woking" in name or "vets" in name or\
                  "vintage" in name or "ladies" in name or "racketball" in name):
                add("Teams")
            elif "junior" in name:
                add("Junior Coaching")
            elif booking.event_type in ["I", ""]:
                add("Members")
            else:
                add("Other")
        results = [result_t(key, val[0]/45, float(val[0])/total, val[1]/45, float(val[1])/total_peak) for key,val in results.iteritems()]
        results.sort(key=lambda x: x.slots, reverse=True)
        return results, [COL_T("Type", "booking_type", None, 3),
                         COL_T("All (45m) Slots", "slots", None, 5),
                         COL_T("", "fraction", "percent", 2),
                         COL_T("Peak Slots", "peak_slots", None, 3),
                         COL_T("", "peak_fraction", "percent", 2),
        ]

    def get_player_activity_data(self):
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
                                        len(p_matches) + len(p_bookings) + len(p_visits))
            players.append(p_sum)
        return players

    def get_membership_summary(self, activity_data):
        activity_data = dict([(datum.sub.pk, datum) for datum in activity_data])
        sub_types = {}
        results_t = collections.namedtuple("SubT", ["sub_type", "n_members", "n_recent", "n_inactive"])

        subscriptions = Subscription.objects.select_related("player__user", "subscription_type", "season").filter(season__has_ended=False)
        totals = {"sub_type": "", "n_members": 0, "n_recent": 0, "n_inactive": 0}
        for sub in subscriptions:
            new_results = {"sub_type": sub.subscription_type.name, "n_members": 0, "n_recent": 0, "n_inactive": 0}
            sub_type = self._get_or_add_set(sub_types, sub.subscription_type, lambda: new_results)
            sub_type["n_members"] += 1
            if sub.player.user.date_joined.date() > sub.season.start_date:
                sub_type["n_recent"] += 1
            activity = activity_data.get(sub.pk)
#            if activity is None:
#                sub_type["n_inactive"] = "N/A"
            if activity is not None and activity.activity == 0:
                sub_type["n_inactive"] += 1
        results = [results_t(**datum) for datum in sub_types.values()]
        results.sort(key=lambda (x): x.n_members, reverse=True)
        return results, [COL_T("Subscription", "sub_type", None, 6),
                         COL_T("Members", "n_members", None, 3),
                         COL_T("Recently Joined", "n_recent", None, 3),
                         COL_T("Inactive", "n_inactive", "numeric", 3)]

    def create_report(self):
        output = StringIO.StringIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'remove_timezone': True})
        
        alt_color_fmt = {'bg_color': '#EBEDEF'}
        alt_row_format = workbook.add_format(alt_color_fmt)
        formats = {
            "title": {'bold': True,  'font_size': 13},
            "header": {'align': 'center', 'valign': 'vjustify', 'bold': False,  'bottom': 1, 'bg_color': '#AEB6BF'},
            "section_header": {'bold': True,  'underline': True},
            "date": {'num_format': 'd mmm yyyy'},
            "datetime": {'num_format': 'd mmm yyyy HH:MM'},
            "percent": {'num_format': '0.0%'},
            "numeric": {'align': 'right'},
            "total": {'align': 'right', 'bold': True},
        }
        cell_formats = {}
        for key, val in formats.iteritems():
            cell_formats[key] = workbook.add_format(val)
            fmt = val.copy()
            fmt.update(alt_color_fmt)
            cell_formats[key + "_alt"] = workbook.add_format(fmt)

        exec_summary_ws = workbook.add_worksheet("Executive Summary")

        def add_worksheet(name, data, fields, autofilter=False):
            worksheet = workbook.add_worksheet(name)
            worksheet.freeze_panes(1, 0)
            self.write_data_to_sheet(worksheet, data, fields, cell_formats, 0, 0,
                                     alt_row_format, autofilter)
            return worksheet        

        activity_data = self.get_player_activity_data()
        add_worksheet("Member Activity", activity_data,
                      [COL_T("Name", "player.get_ordered_name", None, 25),
                       COL_T("Subscription", "sub.subscription_type.name", None, 15),
                       COL_T("Joined", "player.user.date_joined.date", "date", 15),
                       COL_T("# Matches", "n_matches", None, 12),
                       COL_T("# Bookings", "n_bookings", None, 12),
                       COL_T("# Visits", "n_visits", None, 12),
                       COL_T("Activity", "activity", None, 12),
                      ], autofilter=True)
        add_worksheet("Club Competitions", self.matches,
                      [COL_T("Competition", "competition.group.__unicode__", None, 35),
                       COL_T("Name", "competition.name", None, 15),
                       COL_T("Date", "last_updated.date", "date", 20),
                       COL_T("Match", "get_teams_display", None, 40),
                       COL_T("Score", "get_scores_display", None, 25),
                      ], autofilter=True)
        cudata = self.get_court_usage()
        cudata = self.bucket_court_usage(cudata, 4)
        cuws = add_worksheet("Court Use", cudata,
                             [COL_T("Time", "time", None, 10)] +\
                             [COL_T(dow, dow, "percent", 10) for dow in WEEKDAYS])

        exec_summary_ws.hide_gridlines(2)
        exec_summary_ws.set_column(1, 255, width=3.5) # normal width is 8.43 characters
        image_path = "images/apple-touch-icon-114x114.png"
        absolute_path = finders.find(image_path)
        if absolute_path is None:
            absolute_path = os.path.join("/usr/local/www", image_path)
        exec_summary_ws.insert_image(0, 0, absolute_path, {'positioning': 3, 'x_offset': 10, 'y_offset': 10, 'x_scale': 0.5, 'y_scale': 0.5})
        exec_summary_ws.write(2, 3, "Data for {start:%d %b %Y} to {end:%d %b %Y}".format(start=self.start_date, end=self.end_date), cell_formats["title"])

        row_idx = 6
        exec_summary_ws.write(row_idx, 0, "Membership", cell_formats["section_header"])
        data, fields = self.get_membership_summary(activity_data)
        row_idx += 2
        count = reduce(lambda acc, item: acc+item.n_members, data, 0)
        exec_summary_ws.write(row_idx, 0, "The club has {count} subscribed members as of {today:%d %b %Y}. ".format(count=count, today=datetime.date.today()))
        row_idx += 1
        exec_summary_ws.write(row_idx, 0, "They are divided by subscription type as follows:")
        row_idx += 1

        exec_summary_ws.set_row(row_idx, 30)
        row_idx += self.write_data_to_sheet(exec_summary_ws, data, fields, cell_formats, row_idx, 0, alt_row_format,
                                            autofilter=False, totals=[1,2,3], width_in_cells=True)

        inacative_new_data = [row for row in activity_data if row.activity <= 1 and row.player.user.date_joined.date() > row.sub.season.start_date]
        fields = [COL_T("Name", "player.get_ordered_name", None, 6),
                  COL_T("Joined", "player.user.date_joined.date", "date", 3),
                  COL_T("Matches", "n_matches", None, 2),
                  COL_T("Bookings", "n_bookings", None, 2),
                  COL_T("Visits", "n_visits", None, 2)]

        row_idx += 1
        exec_summary_ws.write(row_idx, 0, "The following *new* members are relatively inactive:", None)
        row_idx += 1
        row_idx += self.write_data_to_sheet(exec_summary_ws, inacative_new_data, fields, cell_formats, row_idx, 0, alt_row_format,
                                            autofilter=False, width_in_cells=True)
        
        row_idx += 2
        exec_summary_ws.write(row_idx, 0, "Court Use", cell_formats["section_header"])
        row_idx += 2
        offence_totals = [0, 0, 0]
        for offence in self.offences:
            if offence.offence == "ns": offence_totals[0] += 1
            else: offence_totals[1] += 1
            if not offence.is_active: offence_totals[2] += 1
        exec_summary_ws.write(row_idx, 0, "In this period, there were {1} recorded late cancellations and {0} no-shows.".format(*offence_totals))
        row_idx += 1
        exec_summary_ws.write(row_idx, 0, "{2} of these offences were later retracted.".format(*offence_totals))
        row_idx += 2
        exec_summary_ws.write(row_idx, 0, "Use of the courts was divided as follows:")
        row_idx += 1
        data, fields = self.get_court_usage_summary()
        row_idx += self.write_data_to_sheet(exec_summary_ws, data, fields, cell_formats, row_idx, 0, alt_row_format,
                                            autofilter=False, totals=[1, 3], width_in_cells=True)

        
        
        def make_court_usage_chart(col_range):
            chart = workbook.add_chart({'type': 'column'})
            chart.set_size({'width': 500})
            chart.set_y_axis({"max": 1, 'num_format': '0%'})
            for dow in col_range:
                chart.add_series({
                    'values': [cuws.name, 1, dow, len(cudata), dow],
                    'categories': [cuws.name, 1, 0, len(cudata), 0],
                    'name': [cuws.name, 0, dow]})
            return chart

        row_idx += 1
        exec_summary_ws.write(row_idx, 0, "Court utilization at different times of the week is shown in the following charts:")
        row_idx += 2
        exec_summary_ws.insert_chart(row_idx, 0, make_court_usage_chart(range(1,6)))
        row_idx += 15
        exec_summary_ws.insert_chart(row_idx, 0, make_court_usage_chart(range(6,8)))
        row_idx += 15

        cudata = self.bucket_court_usage(cudata, 2)
        row_headers = [row[0].split("-")[0] + "-" for row in cudata]
        rows = [row[1:] for row in cudata]
#        cudata = zip(*cudata)
        row_idx = self.write_heatmap(workbook, exec_summary_ws, rows, cell_formats, row_headers, WEEKDAYS, row_idx, 0)
        row_idx += 2
        
        exec_summary_ws.write(row_idx, 0, "Internal Competitions", cell_formats["section_header"])
        row_idx += 2
        player_ids = set()
        for comp in self.competitions:
            for entrant in comp.entrant_set.all():
                if entrant.player1_id is not None: player_ids.add(entrant.player1_id)
                if entrant.player2_id is not None: player_ids.add(entrant.player2_id)                
        exec_summary_ws.write(row_idx, 0, "Over this period, {count} members signed up for competitive squash organised by the club.".format(count=len(player_ids)))
        row_idx += 2
        exec_summary_ws.write(row_idx, 0, "A total of {count} matches were played, in the following competitions".format(count=self.matches.count()))
        row_idx += 1
        data, fields = self.get_match_summary()
        row_idx += self.write_data_to_sheet(exec_summary_ws, data, fields, cell_formats, row_idx, 0, alt_row_format,
                                            autofilter=False, totals=[2], width_in_cells=True)

        row_idx += 1
        exec_summary_ws.write(row_idx, 0, "Note that racketball and junior competitions are not currently captured in this data.")
        workbook.close()
        return output.getvalue()
