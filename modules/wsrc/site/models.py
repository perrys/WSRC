from django.db import models
from django.contrib.auth.models import User

import re

class PageContent(models.Model):
  page = models.CharField(max_length=32)
  markup = models.TextField()
  last_updated = models.DateTimeField(auto_now=True)
  
  def __unicode__(self):
    return self.page

class BookingSystemEvent(models.Model):
  start_time = models.DateTimeField()
  end_time = models.DateTimeField()
  court = models.SmallIntegerField()
  description = models.CharField(max_length=64, blank=True, null=True)

class SquashLevels(models.Model):
  name = models.CharField(max_length=64)
  category = models.CharField(max_length=16)
  num_events = models.IntegerField()
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
