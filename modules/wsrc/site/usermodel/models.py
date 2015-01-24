from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.core.mail import send_mail
from django.core import validators
from django.utils.translation import ugettext_lazy as _

import re

class Player(models.Model):
  user = models.OneToOneField(User)

  phone_validator = validators.RegexValidator(re.compile('^\+?[\d ]+$'), _('Enter a valid phone number.'), 'invalid')

  cell_phone  = models.CharField(_('mobile phone'), max_length=30, validators = [phone_validator], blank=True)
  other_phone = models.CharField(_('other phone'), max_length=30, validators = [phone_validator], blank=True)
  short_name  = models.CharField(_('short name'), max_length=32, blank=True)
  squashlevels_id  = models.IntegerField(db_index=True, blank=True, null=True)

#  def get_absolute_url(self):
#      return "/users/%s/" % urlquote(self.user.email)

  def get_full_name(self):
      """
      Returns the first_name plus the last_name, with a space in between.
      """
      full_name = '%s %s' % (self.user.first_name, self.user.last_name)
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

  def __unicode__(self):
    return self.get_full_name()

def create_player_profile(sender, instance, created, **kwargs):  
    if created:  
       profile, created = Player.objects.get_or_create(user=instance)  

post_save.connect(create_player_profile, sender=User) 
