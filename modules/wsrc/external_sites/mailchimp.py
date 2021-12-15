 This file is part of WSRC.
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

"""Manages synchronization of mailchimp mailing lists"""

import logging
import json
import httplib

import wsrc.external_sites # call __init__.py

from wsrc.site.models import OAuthAccess
from wsrc.site.competitions.models import CompetitionGroup
from wsrc.site.usermodel.models import Subscription
from wsrc.utils import url_utils, email_utils

from wsrc.site.settings import settings

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

class EmailUser(object):
    def __init__(self, player):
        self.player = player
        self.attributes = dict()
    def add_attribute(self, key, attrib):
        attrib_list = self.attributes.get(key)
        if attrib_list is None:
            self.attributes[key] = attrib_list = []
        attrib_list.append(attrib)

class AuthException(Exception):
    pass

class APIException(Exception):
    def __init__(self, title, detail, link):
        super(APIException, self).__init__(title)
        self.title = title
        self.detail = detail
        self.link = link
    def __str__(self):
        return "{title}: {detail}\n{link}".format(**self.__dict__)

class MailChimpSession:

    def __init__(self):
        self.oauth_record = OAuthAccess.objects.get(name="MailChimp")
        data = self.api_request(self.oauth_record.auth_server_uri, self.oauth_record.metadata_endpoint, "GET")
        if "error" in data:
            raise AuthException(data["error"])
        LOGGER.info("Logged into mailchimp - account_name: \"%s\", role: \"%s\", endpoint: %s",
                    data["accountname"], data["role"], data["api_endpoint"])
        self.server_uri = data["api_endpoint"]
        self.list_id = settings.MAILCHIMP_LIST_ID
        self.list_info = self.api_get("/lists/{id}".format(id=self.list_id))

    @classmethod
    def is_subscribed(clz, player):
        pref = player.prefs_receive_email
        return pref == True

    def sync(self):
        member_map = self.get_users()
        LOGGER.info("Found: %s unique email addresses with current subscriptions", len(member_map))
        category_to_interest_map_map = self.sync_interest_groups(member_map)
        return self.sync_users(member_map, category_to_interest_map_map)

    def sync_interest_groups(self, member_map):
        category_to_interest_map_map = dict()
        for user in member_map.itervalues():
            for category, vals in user.attributes.iteritems():
                interest_map = category_to_interest_map_map.get(category)
                if interest_map is None:
                    interest_map = category_to_interest_map_map[category] = dict()
                for val in vals:
                    interest_map[val] = None

        endpoint = "/lists/{id}/interest-categories".format(id=self.list_id)
        categories = self.api_get(endpoint)["categories"]
        categories_map = dict([(cat["title"], cat["id"]) for cat in categories])

        for category, user_interest_map in category_to_interest_map_map.iteritems():
            LOGGER.info("Checking category \"%s\"", category)
            cat_id = categories_map.get(category)
            if cat_id is None:
                cat_id = self.api_add(endpoint, {"title": category, "type": "hidden"})["id"]
                categories_map[category] = cat_id
            cat_endpoint = "{endpoint}/{id}/interests".format(endpoint=endpoint, id=cat_id)
            cat_data = self.api_get(cat_endpoint)
            mailchimp_interest_map = dict([(cat["name"], cat["id"]) for cat in cat_data["interests"]])
            for val in user_interest_map.keys():
                LOGGER.info("Checking category entry \"%s\"", val)
                interest_id = mailchimp_interest_map.get(val)
                if interest_id is None:
                    interest_id = self.api_add(cat_endpoint, {"name": val})["id"]
                user_interest_map[val] = interest_id
        return category_to_interest_map_map


    def sync_users(self, member_map, category_to_interest_map_map):
        mailchimp_list = self.api_get("/lists/{id}/members?count=9999".format(id=self.list_id))
        to_remove = []
        mailchimp_map = dict()
        for mailchimp_record in mailchimp_list["members"]:
            db_id = mailchimp_record["merge_fields"].get("DB_ID")
            if db_id is not None:
                try:
                    db_id = int(db_id)
                    if db_id > 0: # ignore negative ids, which are acknowleged skipped emails
                        mailchimp_map[db_id] = mailchimp_record
                except ValueError:
                    LOGGER.warning("invalid db_id: \"%s\"", db_id)
            else:
                to_remove.append(mailchimp_record)
        if len(to_remove) > 0:
            LOGGER.warning("Found %s mailchimp entries without DB_ID", len(to_remove))

        subscribed_ids = set([key for key,val in member_map.items() if self.is_subscribed(val.player)])
        mailchimp_ids = set(mailchimp_map.keys())

        errors = []
        for db_id in mailchimp_ids - subscribed_ids:
            # we have an id in mailchimp not in our subscribed list
            mailchimp_record = mailchimp_map[db_id]
            if mailchimp_record.get("status") == "unsubscribed" or mailchimp_record["merge_fields"].get("UNSUB_SYNC", 0) == 1:
                # person unsubscribed at some point - leave for merge logic
                continue
            # simple case - our member's subs lapsed or they removed
            # their email preference, so we will just take them out of
            # the list:
            to_remove.append(mailchimp_record)

        LOGGER.info("Have %s email address(es) to remove", len(to_remove))
        errors.extend(self.remove(to_remove))

        to_add = subscribed_ids - mailchimp_ids
        LOGGER.info("Have %s email address(es) to add", len(to_add))
        errors.extend(self.add(member_map, to_add, category_to_interest_map_map))

        # take the intersection of all DB members and mailchimp records
        to_compare = set(member_map.keys()).intersection(mailchimp_ids)
        LOGGER.info("Have %s email address(es) to compare", len(to_compare))
        errors.extend(self.compare(mailchimp_map, member_map, to_compare, to_remove, category_to_interest_map_map))

        return errors

    def remove(self, records):
        errors = []
        for mailchimp_record in records:
            endpoint = "/lists/{id}/members/{hash_id}".format(id=self.list_id, hash_id=mailchimp_record["id"])
            try:
                LOGGER.info("Removing %s", mailchimp_record["email_address"])
                self.api_delete(endpoint)
            except APIException, exc:
                errors.append(exc)
        return errors

    def add(self, member_map, to_add, category_to_interest_map_map):
        endpoint = "/lists/{id}/members".format(id=self.list_id)
        errors = []
        for player_id in to_add:
            email_user = member_map[player_id]
            data = {
                "email_address": email_user.player.user.email,
                "status": "subscribed",
                "merge_fields": {
                    "FNAME": email_user.player.user.first_name,
                    "LNAME": email_user.player.user.last_name,
                    "DB_ID": email_user.player.id,
                    "UNSUB_SYNC": 0
                }
            }
            interests = {}
            for category, vals in email_user.attributes.iteritems():
                interest_map = category_to_interest_map_map[category]
                for val in vals:
                    interest_id = interest_map[val]
                    interests[interest_id] = True
            data["interests"] = interests
            try:
                LOGGER.info("Adding %s %s: %s",
                            email_user.player.user.first_name, email_user.player.user.last_name, email_user.player.user.email)
                self.api_add(endpoint, data)
            except APIException, exc:
                errors.append(exc)
        return errors

    def compare(self, mailchimp_map, member_map, to_compare, already_removed_records, category_to_interest_map_map):
        errors = []
        for db_id in to_compare:
            mailchimp_record = mailchimp_map[db_id]
            if mailchimp_record in already_removed_records:
                continue

            member = member_map[db_id]
            endpoint = "/lists/{id}/members/{hash_id}".format(id=self.list_id, hash_id=mailchimp_record["id"])

            if mailchimp_record["status"] == "unsubscribed":
                # this person unsubscribed themselves at some point, may need to sync back to our DB
                if mailchimp_record["merge_fields"].get("UNSUB_SYNC", 0) != 1:
                    LOGGER.info("Unsubscribe request from %s, reason: \"%s\"", member.player.user.get_full_name(),
                                mailchimp_record.get("unsubscribe_reason"))
                    member.player.prefs_receive_email = False
                    member.player.save()
                    updates = {
                        "merge_fields": {"UNSUB_SYNC": 1}
                    }
                    LOGGER.info("Marking unsubscribe synced for %s", member.player.user.email)
                    self.api_update(endpoint, updates)
                elif member.player.prefs_receive_email:
                    # tricky situation - they resubscribed themselves
                    # on our database, but mailchimp will not let us
                    # resubscribe them programatically. They will need
                    # to fill in the list signup form
                    errors.append(Exception("Cannot resubscribe \"{0} <{1}>\", they need to sign up via:\n\n{2}"\
                                            .format(member.player.user.get_full_name(), member.player.user.email,
                                                    self.list_info["subscribe_url_long"])))
                continue # no further processing on unsubscribed records
            elif mailchimp_record["status"] == "cleaned":
                errors.append(Exception("Mailchimp cleaned \"{0} <{1}>\", probably due to hard bounce"\
                                        .format(member.player.user.get_full_name(), member.player.user.email)))
                continue # no further processing on cleaned records

            assert mailchimp_record["status"] == "subscribed"
            if member.player.prefs_receive_email is False:
                # this person has resubscribed to mailchimp - reflect that back to our DB
                LOGGER.info("Subscribe request from %s, syncing to database", member.player.user.get_full_name())
                member.player.prefs_receive_email = True
                member.player.save()

            expected_interests = {}
            for cat_name, interest_map in category_to_interest_map_map.iteritems():
                user_interests = member.attributes.get(cat_name, [])
                for interest, interest_id in interest_map.iteritems():
                    expected_interests[interest_id] = interest in user_interests
            expected_merge_fields = {
                u"LNAME": member.player.user.last_name,
                u"FNAME": member.player.user.first_name,
                u"DB_ID": int(member.player.id),
                u"UNSUB_SYNC": 0
            }

            def different_interests(lhs, rhs):
                ticked_fields = lambda(x): [key for key, val in x.iteritems() if val]
                lhs, rhs = [set(ticked_fields(x)) for x in (lhs, rhs)]
                return lhs != rhs

            if mailchimp_record["merge_fields"] != expected_merge_fields or \
               different_interests(mailchimp_record["interests"], expected_interests) or \
               mailchimp_record["email_address"] != member.player.user.email:
                updates = {
                    "merge_fields": expected_merge_fields,
                    "interests": expected_interests,
                    "email_address": member.player.user.email
                }
                LOGGER.info("Updating %s", member.player.user.email)
                self.api_update(endpoint, updates)
        return errors
    def get_users(self):
        subs = Subscription.objects.filter(season__has_ended=False, player__user__email__isnull=False)\
                                   .select_related("player__user", "subscription_type")\
                                   .prefetch_related("player__user__groups")

        # mailchimp only allows one entry in the list per email. When
        # we have multiple members in our DB with the same address
        # (e.g. juniors with parents' email) , we just pick the most
        # "senior" one and sync them to the list. If members want
        # separate emails for juniors they will need to use individual
        # email addresses.
        emails = dict()
        for sub in subs:
            email = sub.player.user.email.lower().strip()
            if len(email) == 0:
                continue
            subs_with_email = emails[email] = emails.get(email, [])
            subs_with_email.append(sub)

        def seniority_cmp(lhs, rhs):
            # first compare by age
            lhsdob, rhsdob = [x.player.date_of_birth for x in (lhs, rhs)]
            lhsdob, rhsdob = [x.toordinal() if x is not None else 0 for x in (lhsdob, rhsdob)]
            result = lhsdob - rhsdob
            if result == 0: # fall back to membership id
                result = lhs.player.id - rhs.player.id
            return int(result)

        subs = []
        for subs_with_email in emails.itervalues():
            if len(subs_with_email) > 1:
                subs_with_email.sort(seniority_cmp)
            subs.append(subs_with_email[0]) # earliest DoB or earliest db id

        # now we have a unique set of emails, add other attributes:
        members = dict()
        for sub in subs:
            # subs type and entitlement groups:
            members[sub.player.id] = user = EmailUser(sub.player)
            user.add_attribute("Subscription", sub.subscription_type.name)
            user.add_attribute("Gender", sub.player.get_gender_display())
            for group in sub.player.user.groups.all():
                user.add_attribute("Roles", group.name)

        # competitions entered:
        def attribute(players, comp_name):
            for player in players:
                user = members.get(player.id)
                if user is not None:
                    user.add_attribute("Competitions", comp_name)

        league_players = CompetitionGroup.get_comp_entrants("squash_boxes")
        squash57_players = CompetitionGroup.get_comp_entrants("squash57_boxes")
        tournament_players = CompetitionGroup.get_comp_entrants("tournaments")
        attribute(league_players, "Squash Leagues")
        attribute(squash57_players, "Squash57 Leagues")
        attribute(tournament_players, "Tournaments")
        return members

    def api_get(self, endpoint):
        return self.api_request(self.server_uri, "/3.0" + endpoint, "GET")

    def api_delete(self, endpoint):
        return self.api_request(self.server_uri, "/3.0" + endpoint, "DELETE")

    def api_add(self, endpoint, data):
        return self.api_request(self.server_uri, "/3.0" + endpoint, "POST", json.dumps(data))

    def api_update(self, endpoint, data):
        return self.api_request(self.server_uri, "/3.0" + endpoint, "PATCH", json.dumps(data))

    def api_request(self, server, endpoint, method, body=None):
        headers = {
            "user-agent": "oauth2-draft-v10",
            "Authorization": "OAuth " + self.oauth_record.access_token.encode('UTF-8')
        }
        headers, data = url_utils.request(server + endpoint, method, headers=headers, body=body)
        if headers.status >= httplib.BAD_REQUEST:
            if "json" in headers.get("content-type"):
                data = json.loads(data)
                raise APIException(data["title"], data["detail"], data["type"])
        elif headers.status == httplib.NO_CONTENT:
            return None
        return json.loads(data)

def raise_alert(msg):
    address = "membership@wokingsquashclub.org"
    email_utils.send_email("MailChimp Sync Error(s)", msg, None, address, [address])

def sync():
    try:
        session = MailChimpSession()
        errors = session.sync()
        if len(errors) > 0:
            body = ""
            for error in errors:
                body += unicode(error)
                body += "\n\n"
            raise_alert(body)

    except AuthException, exc:
        raise_alert("Access token refused: {0}. Please log into the admin site and refresh".format(exc))
        raise exc

    except OAuthAccess.DoesNotExist, exc:
        raise_alert("No oauth access token - please log into the admin site and refresh")
        raise exc


if __name__ == "__main__":
    import unittest
    from django.contrib.auth.models import User
    from wsrc.site.usermodel.models import Player

    class Tester(unittest.TestCase):

        def setUp(self):
            pass

        def tearDown(self):
            pass

        def test_GIVEN_positive_email_preference_WHEN_assessing_whether_subscribed_THEN_is_true(self):
            user = User.objects.first()
            player = Player(user=user, prefs_receive_email=True)
            self.assertTrue(MailChimpSession.is_subscribed(player))

        def test_GIVEN_negative_email_preference_WHEN_assessing_whether_subscribed_THEN_is_false(self):
            user = User.objects.first()
            player = Player(user=user, prefs_receive_email=False)
            self.assertFalse(MailChimpSession.is_subscribed(player))

        def test_GIVEN_ambiguous_email_preference_WHEN_assessing_whether_subscribed_THEN_is_false(self):
            user = User.objects.first()
            player = Player(user=user, prefs_receive_email=None)
            self.assertFalse(MailChimpSession.is_subscribed(player))

    unittest.main()
