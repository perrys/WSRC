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

"Models for membership and subscriptions"

from django.db import models
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core import validators
from django.db.models import Q

import datetime
import re

import wsrc.site.accounts.models as account_models

class Player(models.Model):

    user = models.OneToOneField(User)

    phone_validator = validators.RegexValidator(re.compile('^\+?[\d ]+$'), ('Enter a valid phone number.'), 'invalid')

    cell_phone  = models.CharField(('Mobile Phone'), max_length=30, validators = [phone_validator], blank=True)
    other_phone = models.CharField(('Other Phone'), max_length=30, validators = [phone_validator], blank=True)
    short_name  = models.CharField(("Short Name"), max_length=32, blank=True)

    wsrc_id  = models.IntegerField(("WSRC ID"), db_index=True, blank=True, null=True,
                                   help_text="Index in the membership spreadsheet")
    booking_system_id  = models.IntegerField(("Booking Site ID"), db_index=True, blank=True, null=True,
                                             help_text="ID in the booking system")
    squashlevels_id  = models.IntegerField(("SquashLevels ID"), db_index=True, blank=True, null=True,
                                           help_text="ID on the SquashLevels website")
    england_squash_id  = models.CharField(("ES Membership #"), blank=True, null=True, max_length=16,
                                             help_text="England Squash Membership Number")
    prefs_receive_email  = models.NullBooleanField(("Receive Email"), default=True, null=True, blank=True,
                                                   help_text="Uncheck if you do not want to receive emails from the club &mdash; match reminders, news, social events etc.")
    prefs_esra_member  = models.NullBooleanField(("England Squash"), default=True, null=True, blank=True,
                                                 help_text="Uncheck if you do not want to automatically be signed up for England Squash membership (note you will not be able to play in Surrey league competitions or National competitions).")
    prefs_display_contact_details  = models.NullBooleanField(("Visible in List"), default=True, null=True, blank=True,
                                                 help_text="Unset if you do not want your contact details to appear in the membership list (note that this will make it very difficult for anyone to contact you regarding league games etc).")

    subscription_regex  = models.CharField(('Regexp for subscription transactions'), max_length=256, null=True, blank=True)
    date_of_birth = models.DateField("DoB", null=True, blank=True)

    def get_current_subscription(self):
        subscriptions = self.subscription_set.all()
        if subscriptions.count() > 0:
            return subscriptions[0]
        return None
    get_current_subscription.short_description = 'Subscription'

    def get_ordered_name(self, encoding=None):
        """
        Returns the last_name plus the first_name, with a comma in between.
        """
        full_name = '%s, %s' % (self.user.last_name, self.user.first_name)
        if encoding is not None:
            full_name = full_name.encode(encoding)
        return full_name.strip()

    def get_cardnumbers(self):
        """
        Returns a comma-separated list of doorcard numbers.
        """
        return ", ".join([str(d.cardnumber) for d in self.doorcards.all()])

    def get_short_name(self):
        "Returns the short name for the user."
        if self.short_name is None or len(self.short_name) == 0:
            return '%s. %s' % (self.user.first_name[0].upper(), self.user.last_name)
        return self.short_name

    def get_age(self):
        if self.date_of_birth is None:
            return None
        today = datetime.date.today()
        years = today.year - self.date_of_birth.year
        if today.month < self.date_of_birth.month or\
           (today.month == self.date_of_birth.month and today.day < self.date_of_birth.day):
            years -= 1
        return years
    get_age.short_description = "Age"
    get_age.admin_order_field = 'date_of_birth'
    
    
    def email_user(self, subject, message, from_email=None):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.user.email])

    @staticmethod
    def get_player_for_user(user):
        player = None
        try:
            if hasattr(user, "player"):
                player = user.player
        except Player.DoesNotExist:
            pass
        return player

    def __unicode__(self):
        return self.get_ordered_name()

    class Meta:
        ordering=["user__last_name", "user__first_name"]
        verbose_name = "Member"


class Season(models.Model):
    start_date = models.DateField(db_index=True, unique=True)
    end_date = models.DateField(db_index=True, unique=True)
    has_ended = models.BooleanField("Has Ended", db_index=True, default=False,
                                    help_text="Indicates no longer relvant for input forms")
    unique_together = ("start_date", "end_date")
    def __unicode__(self):
        return "{start_date:%Y}-{end_date:%y}".format(**self.__dict__)
    @staticmethod
    def latest():
        qs = Season.objects.filter(has_ended=False).order_by("-start_date")
        if qs.count() > 0:
            return qs[0]
        return None
    class Meta:
        ordering = ["start_date"]

class SubscriptionType(models.Model):
    short_code = models.CharField(max_length=16)
    name = models.CharField(max_length=32)
    is_default = models.BooleanField(default=False, help_text="Please ensure only one " +
                                     "subscription type is set as default")
    max_age_years = models.IntegerField(blank=True, null=True)
    def __unicode__(self):
        return self.name
    class Meta:
        verbose_name = "Subscription Type"
        ordering = ["name"]

class SubscriptionCost(models.Model):
    not_ended = Q(has_ended=False)
    season = models.ForeignKey(Season, limit_choices_to=not_ended, related_name="costs")
    subscription_type = models.ForeignKey(SubscriptionType)
    amount = models.FloatField(u"Cost (\xa3)")
    joining_fee = models.FloatField(u"Joining Fee (\xa3)", default=0)
    class Meta:
        verbose_name = "Subscription Cost"
        ordering = ["-season", "-amount"]

class Subscription(models.Model):
    PAYMENT_TYPES = (
        ("annual", "Annually", 1),
        ("triannual", "Tri-annually", 3),
        ("querterly", "Quarterly", 4),
        ("monthly", "Monthly", 12),
    )
    PAY_TYPE_CHOICES = [(ptype[0], ptype[1]) for ptype in PAYMENT_TYPES]
    is_active = Q(user__is_active=True)
    not_ended = Q(has_ended=False)
    # pylint: disable=bad-whitespace
    player            = models.ForeignKey(Player, db_index=True, limit_choices_to=is_active)
    subscription_type = models.ForeignKey(SubscriptionType)
    season            = models.ForeignKey(Season, db_index=True, limit_choices_to=not_ended)
    pro_rata_date     = models.DateField("Pro Rata Date", blank=True, null=True)
    payment_frequency = models.CharField("Payment Freq", max_length=16, choices=PAY_TYPE_CHOICES)
    signed_off        = models.BooleanField("Signoff", default=False)
    comment           = models.TextField(blank=True, null=True)

    unique_together = ("player", "season")

    def payments_count(self):
        return self.payments.count()
    payments_count.short_description = "# Paymnts"

    def get_total_payments(self):
        "Total payments calculated from objects - use when prefetch_related has been called on the queryset"
        total = 0.0
        for s in self.payments.all():
            total += s.transaction.amount
        return total

    def get_subscription_cost(self):
        "Payment due - try to ensure prefetch_related has been called on the queryset"
        sub_costs = self.season.costs.all()
        amount = None
        for cost in sub_costs:
            if cost.subscription_type_id == self.subscription_type_id:
                amount = cost.amount
                break
        if amount is None:
            return 0
        return amount
    get_subscription_cost.short_description = "Subscription Cost"

    def get_pro_rata_cost(self):
        "Amortized cost of subscription"
        amount = self.get_subscription_cost()
        if self.pro_rata_date is not None:
            fraction = max(0, (self.season.end_date - self.pro_rata_date).days) / 365.0
            amount *= fraction
        return amount
    get_pro_rata_cost.short_description = "Pro Rata Cost"

    def get_due_amount(self):
        npayments = 1
        for frt in Subscription.PAYMENT_TYPES:
            if frt[0] == self.payment_frequency:
                npayments = frt[2]
                break
        segment_days = 365.0/npayments
        today = datetime.date.today()
        elapsed_days = max(0, today.toordinal() - self.season.start_date.toordinal())
        segment = int(elapsed_days / segment_days) + 1
        cost = self.get_subscription_cost()
        segment_cost = cost / npayments
        due = segment_cost * segment - self.get_total_payments()
        due -= (cost - self.get_pro_rata_cost())
        return due

    def sum_payments(self):
        "Total payments summed on the database - use for single subscriptions when there is no prefetch"
        result = self.payments.all().aggregate(payments=models.Sum('transaction__amount'))
        return result["payments"]

    def match_transaction(self, transaction, subs_category, persist=True):
        def matches(regex):
            def safestring(astr):
                return astr is not None and astr or ""
            return regex is not None and (regex.search(safestring(transaction.bank_memo)) \
                                          or regex.search(safestring(transaction.comment)))
        def create_payment():
            payment = SubscriptionPayment(subscription=self, transaction=transaction)
            payment.save()
        regex = getattr(self, "subs_regex", None) # cache regex on this object
        if regex is None:
            regex_expr = self.player.subscription_regex
            if regex_expr is not None and len(regex_expr.strip()) > 0:
                self.subs_regex = regex = re.compile(regex_expr, re.IGNORECASE)
        if matches(regex):
            if persist:
                if transaction.category is None:
                    transaction.category = subs_category
                    transaction.save()
                create_payment()
            return True
        # couldn't match using player's regexp. Try their name, but
        # only for transactions already categorized as subscriptions:
        if transaction.category_id == subs_category.id:
            regex = getattr(self, "player_regex", None)
            if regex is None:
                self.player_regex = regex = re.compile(self.player.user.get_full_name(), re.IGNORECASE)
            if matches(regex):
                if persist:
                    create_payment()
                return True
        return False

    def to_short_string(self):
        return u"{0} ({1})".format(self.subscription_type.name, self.season)

    def __unicode__(self):
        return u"{0} ({1}) \u2013 {2}".format(self.player.get_ordered_name(), self.season, self.subscription_type.name)

    class Meta:
        ordering=["-season__start_date", "player__user__last_name", "player__user__first_name"]

class SubscriptionPayment(models.Model):
    subs_transactions_clause = Q(category__name='subscriptions', date_issued__gt='2017-01-01')
    subscription = models.ForeignKey(Subscription, db_index=True, related_name="payments",
                                     limit_choices_to=Q(season__has_ended=False))
    transaction = models.ForeignKey(account_models.Transaction, unique=True,
                                    related_name="subs_payments",
                                    limit_choices_to=subs_transactions_clause)
    def __unicode__(self):
        return u"\xa3{0:.2f} {1}".format(self.transaction.amount, self.subscription)

class DoorEntryCard(models.Model):
    "Many-to-one model for a player's door cards"
    card_validator = validators.RegexValidator(r'^\d{8}$',
                                               'Enter an eight-digit card number.', 'invalid_id')
    player = models.ForeignKey(Player, db_index=True, blank=True, null=True, related_name="doorcards")
    cardnumber = models.CharField("Card #", max_length=8, primary_key=True, validators=[card_validator])
    is_registered = models.BooleanField("Valid",
                                        help_text="Whether card is registred with the card reader",
                                        default=True)
    date_issued = models.DateField("Issue Date", default=datetime.date.today, blank=True, null=True)
    class Meta:
        verbose_name = "Door Entry Card"
    def __unicode__(self):
        result = self.cardnumber
        if self.player is not None:
            result += u" [{0}]".format(self.player.get_ordered_name())
        return result

class DoorCardEvent(models.Model):
    "Events recorded on the cardreader"
    card = models.ForeignKey(DoorEntryCard, blank=True, null=True)
    event = models.CharField(max_length=128, blank=True, db_index=True)
    timestamp = models.DateTimeField(help_text="Timestamp from the cardreader", db_index=True)
    received_time = models.DateTimeField(help_text="Server timestamp", auto_now_add=True)
    class Meta:
        verbose_name = "Door Card Event"


