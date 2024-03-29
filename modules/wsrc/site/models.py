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

import urllib
from django.db import models

import wsrc.site.usermodel.models as user_models
import wsrc.utils.text as text_utils
import wsrc.utils.url_utils as url_utils

class PageContent(models.Model):
    page = models.CharField(max_length=32)
    markup = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.page
    class Meta:
        verbose_name_plural = "Page Templates"

class NavigationNodeManager(models.Manager):
    "Add efficient tree-node manager"
    def tree(self, authenticated=False):
        "Return a list of all nodes, containing NavigationLink instances where appropriate"
        from django.db import connection
        sql = """
SELECT `site_navigationnode`.`id`,
`site_navigationnode`.`name`,
`site_navigationnode`.`parent_id`,
`site_navigationnode`.`ordering`,
`site_navigationnode`.`is_restricted`,
`site_navigationnode`.`icon`,
`site_navigationlink`.`navigationnode_ptr_id`,
`site_navigationlink`.`url`,
`site_navigationlink`.`is_reverse_url`
FROM `site_navigationnode`
LEFT OUTER JOIN `site_navigationlink`  ON ( `site_navigationlink`.`navigationnode_ptr_id` = `site_navigationnode`.`id` )
WHERE `site_navigationnode`.`ordering` IS NOT NULL
"""
        if not authenticated:
            sql += " AND `site_navigationnode`.`is_restricted` = False "
        sql += " ORDER BY `site_navigationnode`.`ordering` DESC"
        cursor = connection.cursor()
        cursor.execute(sql)
        result_list = []
        for row in cursor.fetchall():
            if row[6] is None:
                node = self.model(*row[0:6])
            else:
                node = NavigationLink(*row)
            result_list.append(node)
        return result_list
    
    def parent_nodes(self):
        "Return a queryset excluding navigation nodes which are non-top-level."
        raw_sql = """
SELECT `site_navigationlink`.`navigationnode_ptr_id`
FROM `site_navigationlink`
"""
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute(raw_sql)
        link_ids = [row[0] for row in cursor.fetchall()]
        return self.exclude(id__in=link_ids)

class NavigationNode(models.Model):
    name = models.CharField(max_length=32)
    parent = models.ForeignKey('self', blank=True, null=True, related_name="children", on_delete=models.SET_NULL)
    ordering = models.IntegerField(help_text="higher numbers appear higher", blank=True, null=True)
    is_restricted = models.BooleanField(default=False, help_text="Login required to view")
    icon = models.CharField(max_length=32, blank=True, null=True)
    objects = NavigationNodeManager()
    def __unicode__(self):
        return self.name
    class Meta:
        unique_together = ("parent", "ordering")
        ordering = ["-ordering"]
        verbose_name = "Navigation Node"

class NavigationLink(NavigationNode):
    url = models.CharField(max_length=256)
    is_reverse_url = models.BooleanField(default=False)
    objects = models.Manager()
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = "Navigation Link"

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
    class Meta:
        verbose_name_plural = "Email Templates"

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
    class Meta:
        verbose_name_plural = "Lobby Screen Events"

class NewsItem(models.Model):
    display_date = models.DateField(blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField()
    last_updated = models.DateTimeField(auto_now=True)
    link = models.CharField(max_length=255, blank=True, null=True)
    def __unicode__(self):
        date_str = self.display_date.strftime("%Y-%m-%d") \
                   if self.display_date is not None else ""
        return "{title} {date}".format(title=self.title, date=date_str)
    def tojson(self):
        return {"display_date": self.display_date.strftime("%Y-%m-%d"),
                "title": self.title, "message": self.message, "link": self.link}
    class Meta:
        ordering = ["-display_date"]
        verbose_name = "News Item"
        
class AbstractPDFDocumentModel(models.Model):
    date = models.DateField()

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

class Image(models.Model):    
    image_file = models.FileField(("Image File"), upload_to="images")
    date = models.DateField(auto_now_add=True)
    width = models.IntegerField()
    height = models.IntegerField()
    class Meta:
        ordering = ["-date"]

class SquashLevels(models.Model):
    player = models.ForeignKey(user_models.Player, blank=True, null=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=64)
    num_events = models.IntegerField()
    last_match_date = models.DateField()
    last_match_id = models.IntegerField()
    level = models.IntegerField()
    def __unicode__(self):
        from django.forms.models import model_to_dict
        fields = model_to_dict(self)
        return "{name} ({level})".format(**fields)
    class Meta:
        ordering = ["-level"]

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
    def __unicode__(self):
        from django.forms.models import model_to_dict
        fields = model_to_dict(self)
        return "{date} {team} vs {opponents} ({home_or_away}) ({team1_points} {team2_points})" \
            .format(**fields)
    class Meta:
        ordering = ["date"]

class MaintenanceIssue(models.Model):
    STATUS_VALUES = (
        ("ar", "Awaiting Review"),
        ("aa", "Awaiting Action"),
        ("c", "Complete"),
        ("ni", "Non-issue"),
    )
    reporter = models.ForeignKey(user_models.Player, blank=True, null=True, on_delete=models.PROTECT)
    description = models.TextField()
    reported_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=2, choices=STATUS_VALUES, default="ar")
    target_date = models.DateField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    def __unicode__(self):
        return text_utils.shorten(self.description, 10)
    class Meta:
        verbose_name = "Feedback - Maintenance Issue"


class Suggestion(models.Model):
    suggester = models.ForeignKey(user_models.Player, blank=True, null=True, on_delete=models.PROTECT)
    description = models.TextField()
    submitted_date = models.DateField(auto_now_add=True)
    reviewed_date = models.DateField(blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    class Meta:
        verbose_name = "Feedback - Suggestion"

class OAuthAccess(models.Model):
    GRANT_TYPE_CHOICES = (
        ("client_credentials", "client_credentials"),
        ("authorization_code", "authorization_code")
    )
    name = models.CharField(max_length=16, primary_key=True)
    grant_type = models.CharField(max_length=32, choices=GRANT_TYPE_CHOICES)
    auth_server_uri = models.CharField(max_length=255)
    token_endpoint = models.CharField(max_length=255)
    login_endpoint = models.CharField(max_length=255, blank=True, null=True)
    metadata_endpoint = models.CharField(max_length=255, blank=True, null=True)
    redirect_uri = models.CharField(max_length=255, blank=True, null=True)
    client_id = models.CharField(max_length=255)
    client_secret = models.CharField(max_length=255)
    access_token = models.CharField(max_length=255, blank=True, null=True)

    @property
    def login_link(self):
        if self.login_endpoint is None:
            return None
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri
        }
        return self.auth_server_uri + self.login_endpoint + "?" + urllib.urlencode(params)

    def refresh_access_token(self):
        auth_code = None
        if self.grant_type == "authorization_code":
            # Administrator will need to login to the remote site and enter the
            # temp auth code prior to this:
            auth_code = self.access_token
        url = self.auth_server_uri + self.token_endpoint
        self.access_token = url_utils.get_access_token(url, self.grant_type, self.client_id, \
                                                       self.client_secret, self.redirect_uri, \
                                                       auth_code)
        self.save()

    class Meta:
        unique_together = ("auth_server_uri", "client_id")
        verbose_name = "OAuth Credentials"
        verbose_name_plural = "OAuth Credentials"
