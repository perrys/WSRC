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
from django.core.exceptions import ValidationError
import wsrc.utils.bracket

import wsrc.site.usermodel.models as user_models

# Create your models here.

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
  class Meta:
    ordering=["comp_type", "-end_date"]

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
    ordering=["-group__end_date", "ordering", "name"]


class Entrant(models.Model):
  """Makes up the set of distinct competitors or teams in a competition
     - allows for two players per team (for doubles competitions)"""
  competition = models.ForeignKey(Competition)
  player1 = models.ForeignKey(user_models.Player)
  player2 = models.ForeignKey(user_models.Player, null=True, blank=True, related_name="entrant2+")
  ordering = models.IntegerField("Ordering within a competition - exact meaning depends on the competition type")
  handicap = models.IntegerField(null=True, blank=True)
  hcap_suffix = models.CharField(max_length=4, blank=True)
  seeded = models.BooleanField(default=False) # if true then ordering is interpreted as seeding

  def get_players(self):
    if self.player1 is None:
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

  def __unicode__(self):
    result = u"[{id}] {team}".format(id=self.id, team=self.get_players_as_string())
    if self.handicap:
      result += " ({hcap}{suffix})".format(hcap=self.handicap, suffix=self.hcap_suffix or "")
    else:
      result += " ({ordering})".format(**self.__dict__)
    return  result
  class Meta:
    unique_together = (("competition", "ordering"), ("competition", "player1"),)
    ordering=["-competition__end_date", "competition", "ordering"]

class Match(models.Model):
  """A match which forms part of a competition."""
  WALKOVER_RESULTS = (
    (1, "Team 1"),
    (2, "Team 2"),
  )
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

  def clean(self):
    """Validates the model before it is saved to the database - used when
       data is uploaded in forms e.g. by the generic admin pages.""" 
    if self.team1 is None and self.team2 is None:
      raise ValidationError("Match must have at least one entrant")
    def is_entrant(e):      
      return e is None or self.competition.entrant_set.filter(id=e.id).count() == 1
    if not is_entrant(self.team1):
      raise ValidationError("{entrant} is not part of this competition".format(entrant=self.team1))
    if not is_entrant(self.team2):
      raise ValidationError("{entrant} is not part of this competition".format(entrant=self.team2))

  def get_team(self, team_number_1_or_2):
    entrant = getattr(self, "team%(team_number_1_or_2)d" % locals())
    return entrant or None

  def is_unplayed(self):
    return (self.team1_score1 is None or self.team2_score1 is None) and self.walkover is None

  def get_scores(self):
    def getScore(n):
      s1 = getattr(self, "team1_score%d" % n)
      s2 = getattr(self, "team2_score%d" % n)
      if s1 is not None or s2 is not None:
        return (s1, s2)
      return None
    scores = [getScore(n) for n in range(1,6)]
    return [score for score in scores if score is not None]

  def get_scores_display(self):
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
    t1wins = reduce(lambda total, val: (val[0] > val[1]) and total+1 or total, scores, 0)
    t2wins = reduce(lambda total, val: (val[1] > val[0]) and total+1 or total, scores, 0)
    return (t1wins, t2wins)

  def get_winner(self):
    if self.walkover is not None:
      if self.walkover == 1:
        return self.team1
      else:
        return self.team2

    wins = self.get_sets_won()
    if wins is None:
      return None
    winners = None
    if wins[0] > wins[1]:
      winners = self.team1
    elif wins[0] < wins[1]:
      winners = self.team2
    return winners

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

  def __unicode__(self):
    teams = u""
    if self.team1 is not None:
      teams += self.team1.get_players_as_string()
    if self.team2 is not None:
      if len(teams) > 0:
        teams += " vs "
      teams += self.team2.get_players_as_string()
    buf = u""
    if self.competition_match_id:
      buf += "[{id}] ".format(id=self.competition_match_id)
    buf += "{teams} @{timestamp:%Y-%m-%dT%H:%M}".format(teams=teams, timestamp=self.last_updated)
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
