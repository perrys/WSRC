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

import uuid

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
from django.core.mail import send_mail
from django.core import validators
from django.db.models import Q
from django.contrib.auth.models import AbstractUser

import datetime
import re

import wsrc.site.accounts.models as account_models
from wsrc.utils.text import obfuscate

class AbstractPlayer(models.Model):

    phone_validator = validators.RegexValidator(re.compile('^\+?[\d ]+$'), ('Enter a valid phone number.'), 'invalid')

    PREFS_CHOICES = ((None, 'Not Specified'), (True, "Allow"), (False, "Do Not Allow"))
    PREFS_CHOICES_VIS = ((None, 'Not Specified'), (True, "Visible"), (False, "Not Visible"))

    cell_phone  = models.CharField('Mobile Phone', max_length=30, validators=[phone_validator], blank=True)
    other_phone = models.CharField('Other Phone', max_length=30, validators=[phone_validator], blank=True)

    prefs_receive_email = models.NullBooleanField("Receive General Emails", default=None, null=True, blank=True, choices=PREFS_CHOICES,
                                                  help_text="Allow the club to send you general emails - news, social events, competition reminders etc.")
    prefs_esra_member = models.NullBooleanField("England Squash Enrolment", default=None, null=True, blank=True, choices=PREFS_CHOICES,
                                                help_text="Allow the club to pass on your email address to England Squash, so they can contact you with details of how to activate your membership, which is free as part of your subscription to Woking Squash Rackets Club.")
    prefs_display_contact_details = models.NullBooleanField("Member List Visibility", default=None, null=True, blank=True, choices=PREFS_CHOICES_VIS,
                                                            help_text="Display your contact details in the club's membership list, " +
                                                            "enabling other members to contact you regarding league games etc.")
    date_of_birth = models.DateField("Date of Birth", null=True, blank=True, help_text="Only required for age-restricted subscriptions.")

    class Meta:
        abstract = True


class Player(AbstractPlayer):

    user = models.OneToOneField(User)

    short_name  = models.CharField(("Short Name"), max_length=32, blank=True)

    wsrc_id  = models.IntegerField(("WSRC ID"), db_index=True, blank=True, null=True,
                                   help_text="Index in the membership spreadsheet")
    booking_system_id  = models.IntegerField(("Booking Site ID"), db_index=True, blank=True, null=True,
                                             help_text="ID in the booking system")
    squashlevels_id  = models.IntegerField(("SquashLevels ID"), db_index=True, blank=True, null=True,
                                           help_text="ID on the SquashLevels website")
    england_squash_id  = models.CharField(("ES Membership #"), blank=True, null=True, max_length=16,
                                             help_text="England Squash Membership Number")
    subscription_regex  = models.CharField(('Regexp for subscription transactions'), max_length=256, null=True, blank=True)

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

    def get_obfuscated_name(self):
        """Return an anonomized version of this player's name"""
        return "{0} {1}".format(obfuscate(self.user.first_name, to_initial=True), obfuscate(self.user.last_name))

    def get_cardnumbers(self):
        """
        Returns a comma-separated list of doorcard numbers.
        """
        return ", ".join([str(d.card_id) for d in self.doorcardlease_set.all()])

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

    def get_email_maybe_redacted(self, redacted_value=None):
        return self._redact(self.user.email, redacted_value)

    def get_other_phone_maybe_redacted(self, redacted_value=None):
        return self._redact(self.other_phone, redacted_value)
    
    def get_cell_phone_maybe_redacted(self, redacted_value=None):
        return self._redact(self.cell_phone, redacted_value)
    
    def _redact(self, value, redacted_value=None):            
        if self.prefs_display_contact_details:
            return value
        return redacted_value or "[--redacted--]"
        
    def junior_or_senior(self):
        age = self.get_age()
        if age is not None and age < 19:
            return "Junior"
        return "Senior"

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

    @classmethod
    def latest(claz):
        qs = claz.objects.filter(has_ended=False).order_by("-start_date")
        if qs.count() > 0:
            return qs[0]
        return None

    class Meta:
        ordering = ["start_date"]

def latest_season():
    return Season.latest().pk

class SubscriptionType(models.Model):
    short_code = models.CharField(max_length=16)
    name = models.CharField(max_length=32)
    is_default = models.BooleanField(default=False, help_text="Please ensure only one " +
                                     "subscription type is set as default")
    max_age_years = models.IntegerField(blank=True, null=True)

    @property
    def is_age_sensitive(self):
        return self.max_age_years is not None

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

class AbstractSubscription(models.Model):
    PAYMENT_TYPES = (
        ("annual", "Annually", 1),
        ("triannual", "Tri-annually", 3),
        ("querterly", "Quarterly", 4),
        ("monthly", "Monthly", 12),
    )
    PAY_TYPE_CHOICES = [(ptype[0], ptype[1]) for ptype in PAYMENT_TYPES]
    not_ended = Q(has_ended=False)
    # pylint: disable=bad-whitespace
    subscription_type = models.ForeignKey(SubscriptionType)
    season            = models.ForeignKey(Season, db_index=True, limit_choices_to=not_ended, default=latest_season)
    pro_rata_date     = models.DateField("Pro Rata Date", blank=True, null=True)
    payment_frequency = models.CharField("Payment Freq", max_length=16, choices=PAY_TYPE_CHOICES, default="annual")
    comment           = models.TextField(blank=True, null=True)
    class Meta:
        abstract = True
        
class Subscription(AbstractSubscription):
    is_active = Q(user__is_active=True)
    player = models.ForeignKey(Player, db_index=True, limit_choices_to=is_active)
    signed_off = models.BooleanField("Signoff", default=False)

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

    def is_age_sensitive(self):
        return self.subscription_type.max_age_years is not None

    def clone_to_latest_season(self, latest_season=None):
        if latest_season is None:
            latest_season = Season.latest()
        if self.season_id != latest_season.pk:
            new_sub = Subscription(subscription_type=self.subscription_type,
                                   season=latest_season,
                                   pro_rata_date=None,
                                   payment_frequency=self.payment_frequency,
                                   player=self.player)
            new_sub.save()
            return new_sub
        return self
    
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
    "Unique record for a door card"
    card_validator = validators.RegexValidator(r'^\d{8}$',
                                               'Enter an eight-digit card number.', 'invalid_id')
    cardnumber = models.CharField("Card #", max_length=8, primary_key=True, validators=[card_validator])
    is_registered = models.BooleanField("Card Valid",
                                        help_text="Whether card is currently registred with the card reader",
                                        default=True)
#    player = models.ForeignKey(Player, db_index=True, blank=True, null=True, related_name="doorcards")
#    date_issued = models.DateField("Issue Date", default=datetime.date.today, blank=True, null=True)
    comment = models.TextField(blank=True, null=True)

    def get_current_ownership_data(self, today=None):
        if today is None:
            today = datetime.date.today()
        objects = [obj for obj in self.doorcardlease_set.all() \
                   if obj.date_issued<=today and (obj.date_returned is None or obj.date_returned>=today)]
        nowners = len(objects)
        if nowners == 0:
            return None
        if nowners > 1:
            raise Exception("card {0} has more than one current owner".format(self.cardnumber))
        return objects[0]

    @classmethod
    def sync_cardnumbers(class_, reader_cardnumbers):
        "Update the database using the list of valid numbers from the cardreader"
        reader_cardnumbers = set(reader_cardnumbers)
        recorded_cards = dict([(card.pk, card) for card in class_.objects.all()])
        my_cardnumbers = set(recorded_cards.keys())
        for cardnumber in my_cardnumbers.intersection(reader_cardnumbers):
            # for records we have, ensure is_registered is True
            card = recorded_cards[cardnumber]
            if not card.is_registered:
                card.is_registered = True
                card.save()
        for cardnumber in my_cardnumbers - reader_cardnumbers:
            # records which have no corresponding id on the cardreader - unset is_registered
            card = recorded_cards[cardnumber]
            if card.is_registered:
                card.is_registered = False
                card.save()
        for cardnumber in reader_cardnumbers - my_cardnumbers:
            # cardreader ids which do not have a record in the DB - so create one
            card = class_(cardnumber, is_registered=True)
            card.save()

    class Meta:
        verbose_name = "Door Entry Card"
        ordering=["cardnumber"]
        
    def __unicode__(self):
        result = self.cardnumber
        return result

class DoorCardLease(models.Model):
    "Records non-permanent ownership of a doorcard over a period of time"
    card = models.ForeignKey(DoorEntryCard)
    player = models.ForeignKey(Player, db_index=True)
    date_issued = models.DateField("Issue Date", db_index=True, default=datetime.date.today)
    date_returned = models.DateField("Return Date", db_index=True, blank=True, null=True)
    comment = models.TextField(blank=True, null=True)
    def clean_fields(self, exclude):
        if self.date_returned is not None and self.date_returned < self.date_issued:
            raise ValidationError("Return date must be greater than or equal to issue date")
    def validate_unique(self, exclude):
        super(DoorCardLease, self).validate_unique(exclude)
        this_card_owners = self.__class__.objects.filter(card_id=self.card_id)
        if self.id:
            this_card_owners = this_card_owners.exclude(id=self.id)
        if self.date_returned is None: # indicates current ownership extending to infinite furure time
            if this_card_owners.filter(date_returned__isnull=True).exists():
                err = "Previous owner has not returned this card"
                raise ValidationError({NON_FIELD_ERRORS: ValidationError(err)})
            if this_card_owners.filter(date_issued__gte=self.date_issued).exists():
                err = "Entry would overwrite an existing ownership period"
                raise ValidationError({NON_FIELD_ERRORS: ValidationError(err)})
        else:
            # check our return date does not overlap timespan of any other entries:
            if this_card_owners.filter(date_issued__lte=self.date_returned).filter(
                    models.Q(date_returned__gte=self.date_returned) |\
                    models.Q(date_returned__isnull=True)).exists():
                err = "Return date cannot overlap any other ownership period"
                raise ValidationError({NON_FIELD_ERRORS: ValidationError(err)})
        # check our start date does not overlap any other entries
        if this_card_owners.filter(date_issued__lte=self.date_issued).filter(
                models.Q(date_returned__gte=self.date_issued) |\
                models.Q(date_returned__isnull=True)).exists():
            err = "Issue date cannot overlap any other ownership period"
            raise ValidationError({NON_FIELD_ERRORS: ValidationError(err)})
    
    class Meta:
        verbose_name = "Door Card Lease Period"
        ordering=["player__user__last_name", "player__user__first_name"]
        
    def __unicode__(self):
        result = self.card_id
        return result
    
class DoorCardEvent(models.Model):
    "Events recorded on the cardreader"
    card = models.ForeignKey(DoorEntryCard, blank=True, null=True)
    event = models.CharField("Event Type", max_length=128, blank=True, db_index=True)
    timestamp = models.DateTimeField(help_text="Timestamp from the cardreader", db_index=True)
    received_time = models.DateTimeField(help_text="Server timestamp", auto_now_add=True)
    class Meta:
        verbose_name = "Door Card Event"

class MembershipApplication(AbstractPlayer, AbstractSubscription):
    "Details captured as part of a membership application"

    # from django.contrib.auth.models.AbstractUser:
    username = models.CharField('username', max_length=30, 
                                help_text='Required. 30 characters or fewer. Letters, digits and @/./+/-/_ only.',
                                validators=[
                                    validators.RegexValidator(r'^[\w.@+-]+$', 'Enter a valid username.', 'invalid')
                                ],
                                blank=True, null=True) # user not required to enter this
    first_name = models.CharField('first name', max_length=30)
    last_name = models.CharField('last name', max_length=30)
    email = models.EmailField('email address')

    player = models.ForeignKey(Player, blank=True, null=True)

    guid = models.CharField("GUID", max_length=36, default=uuid.uuid1)
    email_verified = models.BooleanField(default=False)
    signed_off = models.BooleanField(default=False, help_text="Signed off by the membership secretary" +\
                                     " - after which the next save will create this member in the database.")

    def clean_fields(self, *args, **kwargs):
        super(MembershipApplication, self).clean_fields(*args, **kwargs)
        result = {}
        for field in ["prefs_display_contact_details", "prefs_receive_email", "prefs_esra_member"]:
            if getattr(self, field) is None:
                result[field] = ValidationError("You must choose Yes or No.")
        if self.signed_off:
            if not self.email_verified:
                result["email_verified"] = ValidationError("Cannot sign off unless email is verified.")
            if not self.username:
                result["username"] = ValidationError("Cannot sign off without a username.")
        if result:
            raise ValidationError(result)

    def clean(self, *args, **kwargs):
        super(MembershipApplication, self).clean(*args, **kwargs)
        if self.subscription_type_id is not None:
            if self.subscription_type.is_age_sensitive and self.date_of_birth is None:
                err = "Date of birth is required for this subscription type."
                raise ValidationError({"date_of_birth": ValidationError(err)})
            
                
    def validate_unique(self, exclude):
        super(MembershipApplication, self).validate_unique(exclude)
        usernames = [user.username for user in User.objects.all()]
        if self.username in usernames:
            err = "This username already exists."
            raise ValidationError({"username": ValidationError(err)})

    def save(self, *args, **kwargs):
        if not self.guid:
            self.guid = self._meta.get_field("guid").default()
        super(MembershipApplication, self).save(*args, **kwargs)

    def process_application(self, password):
        user = User.objects.create_user(self.username, self.email, password,
                                        first_name=self.first_name, last_name=self.last_name)
        kwargs = dict([(field.name, getattr(self, field.name)) for field in AbstractPlayer._meta.fields])
        member = Player(user=user, **kwargs)
        member.save()
        self.player = member
        self.save()
        kwargs = dict([(field.name, getattr(self, field.name)) for field in AbstractSubscription._meta.fields])
        kwargs["player"] = member
        subscription = Subscription(**kwargs)
        subscription.save()
        
    def __unicode__(self):
        result = "{last_name}, {first_name}".format(**self.__dict__)
        return result
        
    class Meta:
        verbose_name = "Membership Application"
    
