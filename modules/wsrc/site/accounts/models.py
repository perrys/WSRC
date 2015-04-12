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
    ordering=["ordering"]
  
class Transaction(models.Model):
  account = models.ForeignKey(Account)
  date_issued = models.DateField()
  date_cleared = models.DateField(blank=True, null=True)
  amount = models.FloatField()
  category = models.ForeignKey(Category)
  bank_transaction_category = models.CharField(max_length=32, blank=True, null=True)
  bank_number = models.IntegerField(blank=True, null=True)
  bank_memo = models.CharField(max_length=256, blank=True, null=True)
  comment  = models.CharField(max_length=256, blank=True, null=True)
  last_updated = models.DateTimeField(auto_now=True)
  last_updated_by = models.ForeignKey(User)
  def __unicode__(self):
    return "[{account}] {date} {amount} {category}".format(account=self.account.name, date=self.date_issued, amount=self.amount, category=self.category.name)
  
  class Meta:
    ordering=["date_issued", "date_cleared", "category"]

