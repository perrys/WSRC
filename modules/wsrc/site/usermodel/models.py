from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.core.mail import send_mail
from django.core import validators
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q

import re

import wsrc.site.accounts.models as account_models

class Player(models.Model):

  MEMBERSHIP_TYPES = (
    ("coach", "Coach"),
    ("compl", "Complimentary"),
    ("full", "Full"),
    ("junior", "Junior"),
    ("off_peak", "Off-Peak"),
    ("non_playing", "Non-Playing"),
    ("y_adult", "Young Adult"),
    )

  MEMBERSHIP_TYPES_MAP = dict([x for x in MEMBERSHIP_TYPES])

  user = models.OneToOneField(User)

  phone_validator = validators.RegexValidator(re.compile('^\+?[\d ]+$'), ('Enter a valid phone number.'), 'invalid')

  cell_phone  = models.CharField(('Mobile Phone'), max_length=30, validators = [phone_validator], blank=True)
  other_phone = models.CharField(('Other Phone'), max_length=30, validators = [phone_validator], blank=True)
  short_name  = models.CharField(("Short Name"), max_length=32, blank=True)

  membership_type = models.CharField(("Membership Type"), max_length=16, choices=MEMBERSHIP_TYPES)
  wsrc_id  = models.IntegerField(("WSRC ID"), db_index=True, blank=True, null=True,
                                 help_text="Index in the membership spreadsheet")
  booking_system_id  = models.IntegerField(("Booking Site ID"), db_index=True, blank=True, null=True,
                                           help_text="ID in the booking system")
  cardnumber  = models.IntegerField(("Cardnumber"), db_index=True, blank=True, null=True,
                                    help_text="Number on your door entry card")
  squashlevels_id  = models.IntegerField(("SquashLevels ID"), db_index=True, blank=True, null=True, 
                                         help_text="ID on the SquashLevels website")
  england_squash_id  = models.IntegerField(("ES Membership #"), blank=True, null=True, 
                                           help_text="England Squash Membership Number")
  prefs_receive_email  = models.NullBooleanField(("Receive Email"), default=True, null=True, blank=True,
                                                 help_text="Uncheck if you do not want to receive emails from the club &mdash; match reminders, news, social events etc.")
  prefs_esra_member  = models.NullBooleanField(("England Squash"), default=True, null=True, blank=True,
                                               help_text="Uncheck if you do not want to automatically be signed up for England Squash membership (note you will not be able to play in Surrey league competitions or National competitions).")
  prefs_display_contact_details  = models.NullBooleanField(("Visible in List"), default=True, null=True, blank=True,
                                               help_text="Unset if you do not want your contact details to appear in the membership list (note that this will make it very difficult for anyone to contact you regarding league games etc).")

  subscription_regex  = models.CharField(('Regexp for subscription transactions'), max_length=256, null=True, blank=True)
  
  def get_ordered_name(self):
      """
      Returns the last_name plus the first_name, with a comma in between.
      """
      full_name = '%s, %s' % (self.user.last_name, self.user.first_name)
      return full_name.strip()

  def get_short_name(self):
      "Returns the short name for the user."
      if self.short_name is None or len(self.short_name) == 0:
        return '%s. %s' % (self.user.first_name[0].upper(), self.user.last_name)
      return self.short_name

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
    return self.user.get_full_name()

  class Meta:
    ordering=["user__first_name", "user__last_name"]


class Season(models.Model):
  start_date        = models.DateField(db_index=True, unique=True)
  end_date          = models.DateField(db_index=True, unique=True)
  has_ended         = models.BooleanField("Has Ended", help_text="Indicates no longer relvant for input forms", db_index=True, default=False)
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
    ordering=["start_date"]
    

class Subscription(models.Model):
  PAYMENT_TYPES = (
    ("annual", "Annual"),
    ("monthly", "Monthly SO"),
  )
  player            = models.ForeignKey(Player, db_index=True, limit_choices_to=Q(user__is_active=True))
  season            = models.ForeignKey(Season, db_index=True, limit_choices_to=Q(has_ended=False))
  payment_frequency = models.CharField(("Payment Frequency"), max_length=16, choices=PAYMENT_TYPES)
  signed_off        = models.BooleanField("Signed Off", default=False)
  comment           = models.TextField(blank=True, null=True)

  unique_together = ("player", "season")

  def payments_count(self):
    return self.payments.count()
  payments_count.short_description = "# Payments"
  
  def get_total_payments(self):
    "Total payments calculated from objects - use when prefetch_related has been called on the queryset"
    total = 0.0
    for s in self.payments.all():
      total += s.transaction.amount
    return total
  
  def sum_payments(self):
    "Total payments summed on the database - use for single subscriptions when there is no prefetch"
    result = self.payments.all().aggregate(payments=models.Sum('transaction__amount'))
    return result["payments"]

  def match_transaction(self, transaction, subs_category, persist=True):
    def matches(regex):
      return regex is not None and (regex.search(transaction.bank_memo) or regex.search(transaction.comment))
    def create_payment():
      payment = SubscriptionPayment(subscription=self, transaction=transaction)
      payment.save()
    regex = getattr(self, "subs_regex", None) # cache regex on this object 
    if regex is None:
      regex_expr = self.player.subscription_regex
      if regex_expr is not None:
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
    
  
  def __unicode__(self):
    return u"{0} {1}".format(self.player, self.season)

  class Meta:
    ordering=["season__start_date", "player__user__first_name", "player__user__last_name"]
  
class SubscriptionPayment(models.Model):
  subscription = models.ForeignKey(Subscription, db_index=True, related_name="payments",
                                   limit_choices_to=Q(season__has_ended=False))
  transaction = models.ForeignKey(account_models.Transaction, unique=True, related_name="subs_payments",
                                  limit_choices_to=Q(category__name='subscriptions', date_issued__gt='2017-01-01'))
  def __unicode__(self):
    return u"\xa3{0:.2f} {1}".format(self.transaction.amount, self.subscription)
  
