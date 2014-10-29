from django.db import models
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core import validators
from django.utils.translation import ugettext_lazy as _

import re

class Player(models.Model):
  player = models.OneToOneField(User)
  second_email = models.EmailField(_('second email address'), max_length=254, unique=True)
  phone_validator = validators.RegexValidator(re.compile('^\+?[\d ]+$'), _('Enter a valid phone number.'), 'invalid')

  cell_phone = models.CharField(_('mobile phone'), max_length=30, validators = [phone_validator])
  home_phone = models.CharField(_('home phone'), max_length=30, validators = [phone_validator])
  work_phone = models.CharField(_('work phone'), max_length=30, validators = [phone_validator])

  def get_absolute_url(self):
      return "/users/%s/" % urlquote(self.email)

  def get_full_name(self):
      """
      Returns the first_name plus the last_name, with a space in between.
      """
      full_name = '%s %s' % (self.first_name, self.last_name)
      return full_name.strip()

  def get_short_name(self):
      "Returns the short name for the user."
      return self.first_name

  def email_user(self, subject, message, from_email=None):
      """
      Sends an email to this User.
      """
      send_mail(subject, message, from_email, [self.email])
