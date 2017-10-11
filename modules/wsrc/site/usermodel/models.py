from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.core.mail import send_mail
from django.core import validators
from django.utils.translation import ugettext_lazy as _

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
                                    help_text="The number on your door entry card")
  squashlevels_id  = models.IntegerField(("SquashLevels ID"), db_index=True, blank=True, null=True, 
                                         help_text="ID on the squashlevels website - it is not normally necessary to change this")
  england_squash_id  = models.IntegerField(("ES Membership #"), blank=True, null=True, 
                                           help_text="England Squash Membership Number - it is not normally necessary to change this")
  prefs_receive_email  = models.NullBooleanField(("Receive Email"), default=True, null=True, blank=True,
                                                 help_text="Uncheck if you do *not* want to receive emails from the club&emdash; match reminders, social events etc.")

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



class Subscriber(models.Model):  
  player = models.ForeignKey(Player)
  transaction_regex  = models.CharField(('Matching (Regular) Expression'), max_length=256)

class Subscription(models.Model):
  MEMBERSHIP_TYPES = (
    ("coach", "Coach"),
    ("compl", "Complimentary"),
    ("full", "Full"),
    ("junior", "Junior"),
    ("off_peak", "Off-Peak"),
    ("non_playing", "Non-Playing"),
    ("y_adult", "Young Adult"),
    )
  PAYMENT_TYPES = (
    ("annual", "Annual"),
    ("monthly", "Monthly SO"),
  )
  subscriber        = models.ForeignKey(Subscriber, db_index=True)
  membership_type   = models.CharField(("Membership Type"), max_length=16, choices=MEMBERSHIP_TYPES)
  payment_frequency = models.CharField(("Payment Frequency"), max_length=16, choices=PAYMENT_TYPES)
  start_date        = models.DateField(db_index=True)
  end_date          = models.DateField(db_index=True)
  signed_off        = models.BooleanField(default=False, db_index=True)
  
class SubscriptionPayment(models.Model):
  subscription = models.ForeignKey(Subscription, db_index=True)
  transaction = models.ForeignKey(account_models.Transaction, db_index=True)
  
