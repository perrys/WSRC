from django.db import models
from django.contrib.auth.models import User

class Account(models.Model):
  name = models.CharField(max_length=64)
  def __unicode__(self):
    return self.name

class Category(models.Model):
  name  = models.CharField(('Expense/Income Type'), max_length=32)
  description  = models.CharField(('Expense/Income Description'), max_length=128)
  regex  = models.CharField(('Matching (Regular) Expression'), max_length=512)
  ordering = models.IntegerField(unique=True)
  last_updated = models.DateTimeField(auto_now=True)
  last_updated_by = models.ForeignKey(User)
  def __unicode__(self):
    return self.name
  class Meta:
    verbose_name_plural = "categories"
  
class Transaction(models.Model):
  account = models.ForeignKey(Account)
  date = models.DateField()
  amount = models.FloatField()
  category = models.ForeignKey(Category)
  bank_transaction_category = models.CharField(max_length=32, blank=True, null=True)
  bank_number = models.IntegerField(blank=True, null=True)
  bank_memo = models.CharField(max_length=256, blank=True, null=True)
  comment  = models.CharField(max_length=256, blank=True, null=True)
  last_updated = models.DateTimeField(auto_now=True)
  last_updated_by = models.OneToOneField(User)
  def __unicode__(self):
    return "[{name}] {date} {amount} {category} {comment}".format(self.__dict__)
  
  class Meta:
    ordering=["date", "category"]
