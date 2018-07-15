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

"Utility for deleting personal information when no longer required"

import logging

from wsrc.site.usermodel.models import Player, Season, Subscription

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

def to_initial(name):
    return name[:1] + "."

# We don't remove player's names as they are still required for historical
# competition records etc, so just set first name to an initial
PII_FIELDS_TO_PURGE = {"user.email": "",
                       "user.first_name": to_initial,
                       "cell_phone": "",
                       "other_phone": "",
                       "gender": None,
                       "date_of_birth": None,
                       "squashlevels_id": None}

def remove_PII(players):
    count = 0
    for model in players:
        for field, null_value in PII_FIELDS_TO_PURGE.items():
            tmp_model = model
            toks = field.split(".")
            while len(toks) > 1:
                tmp_model = getattr(tmp_model, toks[0])
                toks = toks[1:]
            current_value = getattr(tmp_model, toks[0])
            if hasattr(null_value, "__call__"):
                null_value = null_value(current_value)
            if current_value != null_value:
                setattr(tmp_model, toks[0], null_value)
                count += 1
            if tmp_model != model:
                tmp_model.save()
        model.save()
    LOGGER.info("removed %d piece(s) of personal information", count)
    return count

def remove_DoB(players):
    count = 0
    for model in players:
        if model.date_of_birth is not None:
            model.date_of_birth = None
            model.save()
            count += 1
    LOGGER.info("removed %d date(s) of birth", count)
    return count

def policy_purge_data():
    """Remove all unecessary personal information. Specifically:

    * Remove all personal information for ex-members, except for their name
    * Remove date of birth for members who no longer have age-senstive subscriptions
      (e.g. former Junior/Youth members)

    """
    # Remove all personally identifiable information for ex-members
    ex_members = Player.objects.filter(user__is_active=False)
    remove_PII(ex_members)

    # Remove DoB for members with non-birthdate-dependent subscriptions
    current_season = Season.objects.filter(has_ended=False)[0]
    subscriptions = Subscription.objects.filter(season=current_season,
                                                subscription_type__max_age_years__isnull=True)\
                                        .select_related("player")
    players = [sub.player for sub in subscriptions]
    remove_DoB(players)
