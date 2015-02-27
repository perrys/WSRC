
import wsrc.site.usermodel.models as user_models

from django.db import models
from django.contrib.auth.models import User

import re

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


class BookingSystemEvent(models.Model):
  start_time = models.DateTimeField()
  end_time = models.DateTimeField()
  court = models.SmallIntegerField()
  description = models.CharField(max_length=64, blank=True, null=True)

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
