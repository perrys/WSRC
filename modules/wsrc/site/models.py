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

"General site models"

import wsrc.site.usermodel.models as user_models
import wsrc.utils.text as text_utils

from django.db import models
from django.contrib.auth.models import User

class PageContent(models.Model):
    page = models.CharField(max_length=32)
    markup = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.page

class EmailContent(models.Model):
    TEMPLATE_TYPES = (
        ("django", "Django"),
        ("jinja2", "Jinja 2"),
    )
    name = models.CharField(max_length=32)
    template_type = models.CharField(max_length=16, choices=TEMPLATE_TYPES)
    markup = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.name

class ClubEvent(models.Model):
    title = models.CharField(max_length=64)
    display_date = models.DateField(blank=True, null=True)
    display_time = models.TimeField(blank=True, null=True)
    picture = models.ImageField(upload_to="event_pictures/%Y/%m/%d", blank=True, null=True)
    markup = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)
    def __unicode__(self):
        date_str = self.display_date is not None and\
                   "{display_date:%Y-%m-%d}".format(**self.__dict__) or ""
        return "{title} {date}".format(title=self.title, date=date_str)

class AbstractPDFDocumentModel(models.Model):
    date = models.DateField(auto_now_add=True)

    def get_url(self):
        return self.pdf_file.url

    class Meta:
        abstract = True
        ordering = ["-date"]

class CommitteeMeetingMinutes(AbstractPDFDocumentModel):
    pdf_file = models.FileField(("PDF File"), upload_to="actions")
    class Meta:
        ordering = ["-date"]
        verbose_name = "Committee Actions"
        verbose_name_plural = "Committee Actions"

class GenericPDFDocument(AbstractPDFDocumentModel):    
    pdf_file = models.FileField(("PDF File"), upload_to="pdf_docs")
    class Meta:
        ordering = ["-date"]
        verbose_name = "Document"

        
class SquashLevels(models.Model):
    player = models.ForeignKey(user_models.Player, blank=True, null=True)
    name = models.CharField(max_length=64)
    num_events = models.IntegerField()
    last_match_date = models.DateField()
    last_match_id = models.IntegerField()
    level = models.IntegerField()

class LeagueMasterFixtures(models.Model):
    VENUE_TYPES = (
        ("h", "Home"),
        ("a", "Away"),
    )
    team = models.CharField(max_length=64)
    opponents = models.CharField(max_length=64)
    home_or_away = models.CharField(max_length=1, choices=VENUE_TYPES)
    date = models.DateField()
    team1_score = models.IntegerField(blank=True, null=True)
    team2_score = models.IntegerField(blank=True, null=True)
    team1_points = models.IntegerField(blank=True, null=True)
    team2_points = models.IntegerField(blank=True, null=True)
    url = models.CharField(max_length=128, blank=True, null=True)

class DayOfWeek(models.Model):
    name = models.CharField(max_length=3)
    ordinal = models.IntegerField(unique=True)
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name_plural = "DaysOfTheWeek"
        ordering = ["ordinal"]

class EventFilter(models.Model):
    player = models.ForeignKey(user_models.Player)
    earliest = models.TimeField()
    latest = models.TimeField()
    days = models.ManyToManyField(DayOfWeek, blank=True)
    notice_period_minutes = models.IntegerField("Minimum Notice")
    def __unicode__(self):
        return "EventFilter <%s %s-%s [%s] notice: %s" %\
            (self.player.user.username, self.earliest, self.latest,\
             ",".join([str(d) for d in self.days.all()]), self.notice_period_minutes)

class MaintenanceIssue(models.Model):
    STATUS_VALUES = (
        ("ar", "Awaiting Review"),
        ("aa", "Awaiting Action"),
        ("c", "Complete"),
        ("ni", "Non-issue"),
    )
    reporter = models.ForeignKey(user_models.Player, blank=True, null=True)
    description = models.TextField()
    reported_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=2, choices=STATUS_VALUES, default="ar")
    target_date = models.DateField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    def __unicode__(self):
        return text_utils.shorten(self.description, 10)


class Suggestion(models.Model):
    suggester = models.ForeignKey(user_models.Player, blank=True, null=True)
    description = models.TextField()
    submitted_date = models.DateField(auto_now_add=True)
    reviewed_date = models.DateField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
