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

import wsrc.site.usermodel.models as user_models

# Create your models here.

class CompetitionGroup(models.Model):
  """A grouping of competitions, e.g. a set of league boxes"""
  GROUP_TYPES = (
    ("wsrc_boxes", "Club Leagues"),
    ("wsrc_tournaments", "Club Tournaments"),
  )
  name = models.CharField(max_length=128)
  comp_type = models.CharField(max_length=32, choices=GROUP_TYPES)
  end_date = models.DateField()
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

  def get_winners(self):
    if self.walkover is not None:
      if self.walkover == 1:
        return [self.team1_player1, self.team1_player2]
      else:
        return [self.team2_player1, self.team2_player2]

    wins = [0,0]
    for j in range(1,6):
      def get_score(idx):
        field = "team%(idx)d_score%(j)d" % locals()
        return getattr(self, field)
      scores = [get_score(i) for i in [1,2]]
      if scores[0] > scores[1]:
        wins[0] += 1
      elif scores[0] < scores[1]:
        wins[1] += 1
    if wins[0] > wins[1]:
      winners = [self.team1_player1, self.team1_player2]
    elif wins[0] < wins[1]:
      winners = [self.team2_player1, self.team2_player2]
    else:
      return None


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
