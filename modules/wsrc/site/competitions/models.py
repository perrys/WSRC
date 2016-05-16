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
    maxId = reduce(max, [int(x.competition_match_id) for x in self.match_set.all()], 0)
    return wsrc.utils.bracket.most_significant_bit(maxId)

  def __unicode__(self):
    group_name = self.group is not None and self.group.name or "null"
    return u"%s - %s [%s]" % (group_name, self.name, self.end_date)
  class Meta:
    unique_together = (("group", "ordering"),)
    ordering=["-group__end_date", "ordering", "name"]

class Match(models.Model):
  """A match which forms part of a competition. For singles matches, only player1 is populated for each team"""
  WALKOVER_RESULTS = (
    (1, "Team 1"),
    (2, "Team 2"),
  )
  competition = models.ForeignKey(Competition)
  competition_match_id = models.IntegerField(help_text="Unique ID of this match within its competition", blank=True, null=True)
  team1_player1 = models.ForeignKey(user_models.Player, related_name="match_1_1+", blank=True, null=True)
  team1_player2 = models.ForeignKey(user_models.Player, related_name="match_1_2+", blank=True, null=True)
  team2_player1 = models.ForeignKey(user_models.Player, related_name="match_2_1+", blank=True, null=True)
  team2_player2 = models.ForeignKey(user_models.Player, related_name="match_2_2+", blank=True, null=True)
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

  def get_team_players(self, team_number_1_or_2):
    p1 = getattr(self, "team%(team_number_1_or_2)d_player1" % locals())
    if p1 is None:
      return None
    players = [p1]
    p2 = getattr(self, "team%(team_number_1_or_2)d_player2" % locals())
    if p2 is not None:
      players.append(p2)
    return players

  def get_team_players_as_string(self, team_number_1_or_2):
    opponents = self.get_team_players(team_number_1_or_2)
    if opponents is None:
      return None
    return " & ".join([p.get_full_name() for p in opponents])
    
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

  def get_sets_won(self, scores=None):
    if scores is None:
      scores = self.get_scores()
    if len(scores) == 0:
      return None
    t1wins = reduce(lambda total, val: (val[0] > val[1]) and total+1 or total, scores, 0)
    t2wins = reduce(lambda total, val: (val[1] > val[0]) and total+1 or total, scores, 0)
    return (t1wins, t2wins)

  def get_winners(self):
    if self.walkover is not None:
      if self.walkover == 1:
        return [self.team1_player1, self.team1_player2]
      else:
        return [self.team2_player1, self.team2_player2]

    wins = self.get_sets_won()
    if wins is None:
      return None
    winners = None
    if wins[0] > wins[1]:
      winners = [self.team1_player1, self.team1_player2]
    elif wins[0] < wins[1]:
      winners = [self.team2_player1, self.team2_player2]
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

  def __unicode__(self):
    teams = ""
    if self.team1_player1 is not None:
      teams += self.team1_player1.get_short_name()
    if self.team1_player2 is not None:
      teams += " & " + self.team1_player2.get_short_name()
    if self.team2_player1 is not None:
      if len(teams) > 0:
        teams += " vs "
      teams += self.team2_player1.get_short_name()
    if self.team2_player2 is not None:
      teams += " & " + self.team2_player2.get_short_name()
    return u"%s [%s] %s" % (self.competition_match_id, self.last_updated, teams)
  class Meta:
    verbose_name_plural = "matches"


class CompetitionRound(models.Model):
  """A "round" in a competition. This is used only for tournaments"""
  competition = models.ForeignKey(Competition, related_name="rounds")
  round = models.IntegerField()
  end_date = models.DateField()
  def __unicode__(self):
    return u"%d [%s]" % (self.round, self.end_date)

class Entrant(models.Model):
  # players may not be populated for all types of competitions, as some are inferred from matches:
  competition = models.ForeignKey(Competition)
  player  = models.ForeignKey(user_models.Player)
  player2 = models.ForeignKey(user_models.Player, null=True, blank=True, related_name="entrant2+")
  ordering = models.IntegerField()
  handicap = models.IntegerField(null=True, blank=True)
  hcap_suffix = models.CharField(max_length=4, blank=True)
  seeded = models.BooleanField(default=False)
  def __unicode__(self):
    return u"%s [%d] hcap:(%s%s) <%s>" % (self.player, self.ordering, self.handicap, self.hcap_suffix, self.competition)
  class Meta:
    unique_together = (("competition", "ordering"), ("competition", "player"),)
    ordering=["-competition__end_date", "competition", "ordering"]
