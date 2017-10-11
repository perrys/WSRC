#!/opt/bin/python

import logging
import markdown
import os
import time
import traceback
import unittest

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template import Template, Context

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

EMAIL_DELAY_PERIOD = 2

def send_email(subject, text_body, html_body, from_address, to_list, bcc_list=None, reply_to_address=None, cc_list=None, extra_attachments=None):
  headers = {}
  if reply_to_address is not None:
    headers['Reply-To'] = reply_to_address
  if html_body is not None:
    msg = EmailMultiAlternatives(subject, text_body, from_address,
                                 to_list, bcc_list, headers=headers, cc=cc_list)
    msg.attach_alternative(html_body, "text/html")
    if extra_attachments is not None:
      for content_type, data in extra_attachments.items():
        msg.attach_alternative(data, content_type)        
  else:
    msg = EmailMessage(subject, text_body, from_address,
                       to_list, bcc_list, headers=headers, cc=cc_list)
    if extra_attachments is not None:
      for data in extra_attachments:
        msg.attach(data)        
  LOGGER.debug("sending mail, subject=\"{subject}\", from={from_address}, to_list={to_list}, cc_list={cc_list}, bcc_list={bcc_list}, headers={headers}".format(**locals()))
  msg.send(fail_silently=False)

def send_markdown_email(subject, markdown_body, from_address, to_list, bcc_list=None, reply_to_address=None):
  html_content = markdown.markdown(markdown_body)
  send_email(subject, markdown_body, html_content, from_address, to_list, bcc_list, reply_to_address)

def get_email_bodies(template_name, params):
  from wsrc.site.models import EmailContent
  template_obj = EmailContent.objects.get(name=template_name)
  email_template = Template(template_obj.markup)
  context = Context(params)
  context["content_type"] = "text/html"
  html_body = markdown.markdown(email_template.render(context), extensions=['markdown.extensions.extra'])
  context["content_type"] = "text/plain"
  text_body = email_template.render(context)
  return text_body, html_body
  
class BatchEmailFailure(Exception):

  def __init__(self, message, success_list, reason=None):
    super.__init__(self, EmailFailure, message)
    self.success_list = success_list
    self.reason = reason

def select_members(member_types, honour_email_preferences=True):
  from wsrc.site.usermodel.models import Player
  from django.db.models import Q
  queryset = Player.objects.filter(user__is_active=True)
  queryset = queryset.filter(user__email__isnull=False)
  queryset = queryset.filter(user__email__contains='@')
  if honour_email_preferences:
    queryset = queryset.exclude(prefs_receive_email=False)
  clauses = None
  if member_types is not None:
    for t in member_types:
      clause = Q(membership_type=t)
      if clauses is None:
        clauses = clause
      else:
        clauses = clauses | clause
  if clauses is not None:
    queryset = queryset.filter(clauses)
  return [m for m in queryset]

def bulk_email_membership(subject, markdown_body, from_address, members, batch_size=50):
  success_list = []
  for i in range(0, len(members), batch_size):
    batch = members[i:i+batch_size]
    emails = [member.user.email for member in batch]
    try:
      LOGGER.info("Sending batch of {n} email(s)".format(n=len(emails)))
      send_markdown_email(subject, markdown_body, from_address, ["members@wokingsquashclub.org"], emails, None)
      success_list.extend(batch)
      pause_between_emails()
    except Exception, e:
      raise BatchEmailFailure("Error during batch email", success_list, e)
  return success_list
  
def pause_between_emails():
  time.sleep(EMAIL_DELAY_PERIOD) # some SMTP servers have anti-spammer lock-outs if you send mails too quickly

class tester(unittest.TestCase):

  # a number of these tests rely on certain characteristics of the
  # data in the database. It would perhaps be better to setup a test
  # DB as part of the suite, but it is also reasuring to see these
  # pass with live data

  def setUp(self):
    from wsrc.site.usermodel.models import Player
    self.all_players = Player.objects.all()
    self.assertGreater(len(self.all_players), 0)

    self.active_players_with_email = [p for p in self.all_players if (p.user.is_active and p.user.email is not None and len(p.user.email) > 0)]
    self.assertGreater(len(self.active_players_with_email), 0)
    self.assertLess(len(self.active_players_with_email), len(self.all_players))
    
  def test__given_live_database__when_filtering_membertypes__ensure_appropriate_players_returned(self):
    membertypes = ["full", "junior"]
    set1 = select_members(membertypes)
    example_full_member = None
    for p in set1:
      self.assertIn(p.membership_type, membertypes)
      if example_full_member is None:
        example_full_member = p
    self.assertIsNotNone(example_full_member)
    membertypes = ["junior"]
    set2 = select_members(membertypes)
    self.assertGreater(len(set1), len(set2))
    for p in set2:
      self.assertIn(p.membership_type, membertypes)
      self.assertNotEqual(p.id, example_full_member.id)

  def test__given_live_database__when_selecting_all__ensure_all_players_with_email_returned(self):
    def test_with_list(l):
      test_list = select_members(l, honour_email_preferences=False)
      self.assertEqual(len(self.active_players_with_email), len(test_list))
    test_with_list([])
    test_with_list(None)

  def test__given_live_database__when_selecting_all__ensure_inactive_players_not_returned(self):
    inactive_player_ids = [p.id for p in self.all_players if (p.user.is_active == False)]
    self.assertGreater(len(inactive_player_ids), 0)
    self.assertLess(len(inactive_player_ids), len(self.all_players))
    relevant_players = select_members(None, honour_email_preferences=False)
    for p in relevant_players:
      self.assertNotIn(p.id, inactive_player_ids)

  def test__given_live_database__when_selecting_all__ensure_no_players_with_email_optout_returned(self):
    players_with_email_optout = [p for p in self.all_players if (p.user.email is not None and len(p.user.email) > 0)]
    self.assertGreater(len(players_with_email_optout), 0)
    self.assertLess(len(players_with_email_optout), len(self.all_players))
    email_permitted_players = select_members(None, honour_email_preferences=True) 
    self.assertGreater(len(email_permitted_players), 0)
    self.assertLess(len(email_permitted_players), len(self.active_players_with_email))
    for p in email_permitted_players:
      self.assertTrue((p.prefs_receive_email is None) or p.prefs_receive_email == True)

#  @unittest.skip("requires network and smtp server") # skip property not supported by python 2.6
  def xx_test_emailer(self):
    test_player = None
    for p in self.active_players_with_email:
      if p.user.first_name == "Stewart" and p.user.last_name == "Perry":
        test_player = p
    self.assertIsNotNone(test_player)
    body = "Test *message*"
    success_list = bulk_email_membership("testing testing", body, "foobar@dbsquash.org", [test_player])
    self.assertEqual(1, len(success_list))
    self.assertIn(test_player, success_list)

if __name__ == "__main__":
  
  os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wsrc.site.settings.settings")
  suite = unittest.TestLoader().loadTestsFromTestCase(tester)
  unittest.TextTestRunner(verbosity=2).run(suite)
  exit(0)



