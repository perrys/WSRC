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

"Models for club financials"

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

class Account(models.Model):
    name = models.CharField(max_length=64)
    sort_code = models.CharField(max_length=8, validators=[RegexValidator(r"\d\d-\d\d-\d\d")], blank=True, null=True)
    acc_number = models.CharField(max_length=8, validators=[RegexValidator(r"\d{8}")], blank=True, null=True)
    def __unicode__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(('Expense/Income Type'), max_length=32)
    description = models.CharField(('Expense/Income Description'), max_length=128)
    regex = models.CharField(('Matching (Regular) Expression'), max_length=512)
    ordering = models.IntegerField(unique=True)
    is_reconciling = models.BooleanField(default=False)
    last_updated = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(User)
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name_plural = "categories"
        ordering = ["ordering"]

class Transaction(models.Model):
    account = models.ForeignKey(Account)
    date_issued = models.DateField()
    date_cleared = models.DateField(blank=True, null=True)
    amount = models.FloatField()
    category = models.ForeignKey(Category, db_index=True)
    bank_transaction_category = models.CharField(max_length=32, blank=True, null=True)
    bank_number = models.IntegerField(blank=True, null=True)
    bank_memo = models.CharField(max_length=256, blank=True, null=True)
    comment = models.CharField(max_length=256, blank=True, null=True)
    last_updated = models.DateTimeField(auto_now=True)
    last_updated_by = models.ForeignKey(User)
    def __unicode__(self):
        return u"{0} \u2013 \xa3{1:.2f} \u2013 {2}".format(self.date_issued, self.amount, self.bank_memo)

    class Meta:
        ordering = ["-date_cleared", "category__ordering", "date_issued", "amount", "bank_memo", "comment"]
