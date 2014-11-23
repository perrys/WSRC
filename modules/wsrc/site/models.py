from django.db import models
from django.contrib.auth.models import User

import re

class PageContent(models.Model):
  page = models.CharField(max_length=32)
  markup = models.TextField()
  last_updated = models.DateTimeField(auto_now=True)
  
  def __unicode__(self):
    return self.page

class SquashLevels(models.Model):
  name = models.CharField(max_length=64)
  category = models.CharField(max_length=16)
  events = models.IntegerField()
  level = models.IntegerField()
