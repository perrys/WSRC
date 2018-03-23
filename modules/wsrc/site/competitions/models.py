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

from django.db import models
from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
import wsrc.utils.bracket

import wsrc.site.usermodel.models as user_models

# Create your models here.

class BoxLeaguePoints:
    SCORE_TO_POINTS_MAPPING = {3 : {0: (7, 2), 1: (6, 3), 2: (5, 4)},
                               2 : {0: (4, 2), 1: (4, 3), 2: (4, 4)},
                               1 : {0: (3, 2), 1: (3, 3)},
                               0 : {0: (2, 2)}}
    @classmethod
    def toPoints(self_cls, x, y):
        if x > y:
            tup = (x, y)
            reverse = False
        else:
            tup = (y, x)
            reverse = True
        if tup[0] == 999:
            total = (7, 0)
        else:
            total = self_cls.SCORE_TO_POINTS_MAPPING[tup[0]][tup[1]]
        if reverse:
            return (total[1], total[0])
        return total
    
    

class CompetitionGroup(models.Model):
    """A grouping of competitions, e.g. a set of league boxes"""
    GROUP_TYPES = (
        ("wsrc_boxes", "Club Leagues"),
        ("wsrc_tournaments", "Club Tournaments"),
        ("wsrc_qualifiers", "Club Tournament Qualifiers"),
    )
    name = models.CharField(max_length=128)
    comp_type = models.CharField(max_length=32, choices=GROUP_TYPES)
    end_date = models.DateField()
    # TODO - this field is a less useful duplicate of the state field on
    # competition, and the two are used interchangably in the code. We
    # should remove this one. Group querysets can be filtered using e.g.
    # .exclude(competition__state="not_started")
    active = models.BooleanField(default=False)
    def __unicode__(self):
        return u"%s" % (self.name)

    @staticmethod
    def get_comp_entrants(*group_types):
        "Return a set of Player objects who are entrants in the given competition groups"
        clause = None
        for group_type in group_types:
            q = models.Q(comp_type=group_type)
            if clause is None:
                clause = q
            else:
                clause |= q
        groups = CompetitionGroup.objects.filter(clause).filter(active=True)\
                 .prefetch_related("competition_set__entrant_set__player1", "competition_set__entrant_set__player2")
        players = set()
        for group in groups:
            for comp in group.competition_set.all():
                for entrants in comp.entrant_set.all():
                    players.add(entrants.player1)
                    if entrants.player2 is not None:
                        players.add(entrants.player2)
        return players
    
    class Meta:
        ordering = ["comp_type", "-end_date"]
        verbose_name = "Competition Group"

class Competition(models.Model):
    """An individual competition, with an end date. For example this could be a knockout tournament or a league."""
    STATES = (
        ("not_started", "Not Started"),
        ("active",      "In Process"),
        ("complete",    "Concluded"),
    )
    name = models.CharField(max_length=128)
    state = models.CharField(max_length=16, choices=STATES, default="not_started")
    end_date = models.DateField()
    group = models.ForeignKey(CompetitionGroup, blank=True, null=True)
    url = models.CharField(max_length=128, blank=True)
    ordering = models.IntegerField(blank=True, null=True)

    def nbrackets(self):
        """Only applicable for knockout tournaments - return the number of
           brackets based on the values of competition_match_id for each match."""
        maxId = reduce(max, [int(x.competition_match_id) for x in self.match_set.all()], 0)
        return wsrc.utils.bracket.most_significant_bit(maxId)

    def __unicode__(self):
        group_name = self.group is not None and self.group.name or "null"
        return u"%s - %s [%s]" % (group_name, self.name, self.end_date)

    class Meta:
        unique_together = (("group", "ordering"),)
        ordering = ["-group__end_date", "ordering", "name"]


class Entrant(models.Model):
    """Makes up the set of distinct competitors or teams in a competition
       - allows for two players per team (for doubles competitions)"""
    is_active = models.Q(user__is_active=True)
    competition = models.ForeignKey(Competition)
    player1 = models.ForeignKey(user_models.Player, limit_choices_to=is_active)
    player2 = models.ForeignKey(user_models.Player, limit_choices_to=is_active,\
                                null=True, blank=True, related_name="player2")
    ordering = models.IntegerField(help_text="Exact meaning depends on the competition type")
    handicap = models.IntegerField(null=True, blank=True)
    hcap_suffix = models.CharField(max_length=4, blank=True)
    seeded = models.BooleanField(default=False) # if true then ordering is interpreted as seeding

    def get_players(self):
        if self.player1_id is None:
            return None
        players = [self.player1]
        if self.player2 is not None:
            players.append(self.player2)
        return players

    def get_players_as_string(self):
        opponents = self.get_players()
        if opponents is None:
            return None
        if len(opponents) == 1:
            return opponents[0].user.get_full_name()
        return " & ".join([p.get_short_name() for p in opponents])

    def get_seed_or_handicap(self):
        if self.seeded:
            return self.ordering
        if self.handicap is not None:
            handicap = self.handicap
            if self.hcap_suffix is not None:
                handicap = "{0}{1}".format(self.handicap, self.hcap_suffix)
            return handicap
        return None

    def get_players_as_string_ordered(self):
        opponents = self.get_players()
        if opponents is None:
            return None
        if len(opponents) == 1:
            return opponents[0].get_ordered_name()
        return " & ".join([p.get_ordered_name() for p in opponents])

    def __unicode__(self):
        result = u"{team} [{id}]".format(id=self.id, team=self.get_players_as_string_ordered())
        if self.handicap:
            result += " ({hcap}{suffix})".format(hcap=self.handicap, suffix=self.hcap_suffix or "")
        else:
            result += " ({ordering})".format(**self.__dict__)
        return  result
    class Meta:
        unique_together = (("competition", "ordering"), ("competition", "player1"),)
        ordering = ["-competition__end_date", "competition", "ordering"]

class Match(models.Model):
    """A match which forms part of a competition."""
    WALKOVER_RESULTS = [
        (1, "Opponent 1"),
        (2, "Opponent 2"),
    ]
    competition = models.ForeignKey(Competition)
    competition_match_id = models.IntegerField(help_text="Unique ID of this match within its competition", blank=True, null=True)
    team1 = models.ForeignKey(Entrant, related_name="match_1+", blank=True, null=True)
    team2 = models.ForeignKey(Entrant, related_name="match_2+", blank=True, null=True)
    team1_score1 = models.IntegerField(blank=True, null=True)
    team1_score2 = models.IntegerField(blank=True, null=True)
    team1_score3 = models.IntegerField(blank=True, null=True)
    team1_score4 = models.IntegerField(blank=True, null=True)
    team1_score5 = models.IntegerField(blank=True, null=True)
    team2_score1 = models.IntegerField(blank=True, null=True)
    team2_score2 = models.IntegerField(blank=True, null=True)
    team2_score3 = models.IntegerField(blank=True, null=True)
    team2_score4 = models.IntegerField(blank=True, null=True)
    team2_score5 = models.IntegerField(blank=True, null=True)
    walkover = models.IntegerField(blank=True, null=True, choices=WALKOVER_RESULTS)
    last_updated = models.DateTimeField(auto_now=True)

    def __init__(self, *args, **kwargs):
        super(Match, self).__init__(*args, **kwargs)
        self.cached_scores = None

    def cache_scores(self):
        self.cached_scores = self.get_scores()
        return self

    def clean(self):
        """Validates the model before it is saved to the database - used when
           data is uploaded in forms e.g. by the generic admin pages."""
        if self.team1 is None and self.team2 is None:
            raise ValidationError("Match must have at least one entrant")
        entrants = [entrant.pk for entrant in self.competition.entrant_set.all()]
        def is_entrant(e):
            return e is None or e.pk in entrants
        if not is_entrant(self.team1):
            raise ValidationError("{entrant} is not part of this competition".format(entrant=self.team1))
        if not is_entrant(self.team2):
            raise ValidationError("{entrant} is not part of this competition".format(entrant=self.team2))
        if self.team1 == self.team2:
            raise ValidationError("Two opponents in the same match must be different!")
        if self.walkover is None and (self.team1_score1 is None or self.team2_score1 is None):
            raise ValidationError("At least one score is required, or a walkover")
        if self.competition.group.comp_type == "wsrc_tournaments":
            winner = self.get_winner()
            if winner is None:
                raise ValidationError("Tournament matches must have a winner")

    def validate_unique(self, exclude):
        super(Match, self).validate_unique(exclude)
        matches = self.competition.match_set
        if self.pk:
            matches = matches.exclude(pk=self.pk)
        def order(id1, id2):
            if id1 > id2:
                return (id1, id2)
            return (id2, id1)
        opponents = dict([(order(match.team1_id, match.team2_id), match) for match in matches.all()])
        existing = opponents.get(order(self.team1_id, self.team2_id))
        if existing is not None:
            err = "A match with the same opponents already exists for this competition"
            raise ValidationError({NON_FIELD_ERRORS: ValidationError(err, code="match_exists", params={"match": existing})})

    def save(self, *args, **kwargs):
        super(Match, self).save(*args, **kwargs)
        if self.competition.group.comp_type == "wsrc_tournaments":
            winner = self.get_winner()
            if winner is not None and self.competition_match_id > 1:
                from .tournament import get_or_create_next_match
                get_or_create_next_match(self.competition, self.competition_match_id, winner)
        
    def get_team(self, team_number_1_or_2):
        entrant = getattr(self, "team%(team_number_1_or_2)d" % locals())
        return entrant or None

    def is_unplayed(self):
        return (self.team1_score1 is None or self.team2_score1 is None) and self.walkover is None

    def get_scores(self):
        if self.cached_scores is not None:
            return self.cached_scores
        def getScore(n):
            s1 = getattr(self, "team1_score%d" % n)
            s2 = getattr(self, "team2_score%d" % n)
            if s1 is not None or s2 is not None:
                return (s1, s2)
            return None
        scores = [getScore(n) for n in range(1,6)]
        return [score for score in scores if score is not None]

    def get_scores_display(self, scores=None):
        if scores is None:
            scores = self.get_scores()
        def fmt(s):
            return "-".join([i is not None and "%d" % (i,) or "(None)" for i in s])
        return ", ".join([fmt(s) for s in scores])
    get_scores_display.short_description = "Scores"

    def get_sets_won(self, scores=None):
        if scores is None:
            scores = self.get_scores()
        if len(scores) == 0:
            return None
        t1wins = t2wins = 0
        for score in scores:
            if score[0] > score[1]:
                t1wins += 1
            elif score[1] > score[0]:
                t2wins += 1
        return (t1wins, t2wins)

    def get_box_league_points(self, scores=None):
        if self.walkover is not None:
            points = (self.walkover == 1) and [7, 2] or [2, 7]
        else:
            if scores is None:
                scores = self.get_scores()
            sets_won = self.get_sets_won(scores)
            points = (0, 0)
            if sets_won is not None:
                points = BoxLeaguePoints.toPoints(min(sets_won[0], 3), min(sets_won[1], 3))
        return points

    def get_box_league_points_team1(self, scores=None):
        points = self.get_box_league_points(scores)
        return points[0]
    
    def get_box_league_points_team2(self, scores=None):
        points = self.get_box_league_points(scores)
        return points[1]
    
    def get_winner(self, scores=None, key_only=False):
        def get_entrant(i):
            attr = "team{i}".format(i=i)
            if key_only: attr += "_id"
            return getattr(self, attr)
        if self.walkover is not None:
            if self.walkover == 1:
                return get_entrant(1)
            else:
                return get_entrant(2)

        wins = self.get_sets_won(scores)
        if wins is None:
            return None
        winners = None
        if wins[0] > wins[1]:
            winners = get_entrant(1)
        elif wins[0] < wins[1]:
            winners = get_entrant(2)
        return winners

    def get_winner_of_set(self, setnumber, scores=None, key_only=False):
        "Indicate winner of a particular set [1..5]"
        def get_entrant(i):
            attr = "team{i}".format(i=i)
            if key_only: attr += "_id"
            return getattr(self, attr)
        if scores is None:
            scores = self.get_scores()
        set_scores = scores[setnumber-1] if len(scores) >= setnumber else None
        if set_scores is None:
            return None
        if set_scores[0] > set_scores[1]:
            return get_entrant(1)
        if set_scores[0] < set_scores[1]:
            return get_entrant(2)
        return None

    def is_knockout_comp(self):
        return self.competition.group.comp_type == "wsrc_tournaments"

    def get_round(self):
        if self.competition_match_id is None:
            return None
        rnd = wsrc.utils.bracket.most_significant_bit(self.competition_match_id)
        nbrackets = self.competition.nbrackets()
        nrounds = len(self.competition.rounds.all())
        if nrounds != nbrackets:
            raise Exception("nrounds (%d) != nbrackets (%d) for competition %s" % (nrounds, nbrackets, str(self.competition)))
        return self.competition.rounds.get(round=wsrc.utils.bracket.descending_round_number_to_ascending(rnd, nrounds))

    def get_deadline(self):
        if self.is_knockout_comp():
            return self.get_round().end_date
        return self.competition.end_date

    def get_reverse_gray(self):
        if self.competition_match_id:
            gray = wsrc.utils.bracket.binary_to_gray(self.competition_match_id)
            rev_gray = wsrc.utils.bracket.reverse(gray, wsrc.utils.bracket.most_significant_bit(gray))
            return wsrc.utils.bracket.gray_to_binary(rev_gray)
        return None

    def get_teams_display(self):
        teams = u""
        if self.team1 is not None:
            teams += self.team1.get_players_as_string()
        if self.team2 is not None:
            if len(teams) > 0:
                teams += " vs "
            teams += self.team2.get_players_as_string()
        return teams

    def __unicode__(self):
        teams = self.get_teams_display()
        buf = u""
        if self.competition_match_id:
            buf += "[{id}] ".format(id=self.competition_match_id)
        buf += u"{teams} @{timestamp:%Y-%m-%dT%H:%M}".format(teams=teams, timestamp=self.last_updated)
        return buf
    class Meta:
        verbose_name_plural = "matches"


class CompetitionRound(models.Model):
    """A "round" in a competition. This is used only for tournaments"""
    competition = models.ForeignKey(Competition, related_name="rounds")
    round = models.IntegerField()
    end_date = models.DateField()
    def __unicode__(self):
        return u"%d [%s]" % (self.round, self.end_date)
    class Meta:
        verbose_name = "Competition Round"
