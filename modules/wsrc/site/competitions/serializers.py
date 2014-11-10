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

from django.forms import widgets
from rest_framework import serializers
from django.contrib.auth.models import User

from wsrc.site.usermodel.models import Player
from wsrc.site.competitions.models import CompetitionGroup, Competition, Match, Seeding

SCORE_TO_POINTS_MAPPING = {3 : {0: (7,2), 1: (6,3), 2: (5,4)},
                           2 : {0: (6,2), 1: (4,3), 2: (4,4)},
                           1 : {0: (4,2), 1: (3,3)},
                           0 : {0: (2,2)}}

def toPoints(x, y):
    if x > y:
      tup = (x,y)
      reverse = False
    else:
      tup = (y,x)
      reverse = True
    if tup[0] == 999:
      total = (7,0)
    else:
      total = SCORE_TO_POINTS_MAPPING[tup[0]][tup[1]]
    if reverse:
      return (total[1], total[0])
    return total


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'first_name', 'last_name')


class PlayerSerializer(serializers.ModelSerializer):
  full_name = serializers.CharField(source="get_full_name", read_only="True")
  short_name = serializers.CharField(source="get_short_name", read_only="True")
  class Meta:
    model = Player
    fields = ('id', 'full_name', 'short_name')

class MatchSerializer(serializers.ModelSerializer):
  team1_player1 = team1_player2 = team2_player1 = team2_player2 = PlayerSerializer()
  class Meta:
    model = Match

class CompactMatchField(serializers.RelatedField):
  def to_native(self, match):
    scores = []
    def getScore(n):
      s1 = getattr(match, "team1_score%d" % n)
      s2 = getattr(match, "team2_score%d" % n)
      if s1 is not None or s2 is not None:
        return (s1, s2)
      return None
    scores = [getScore(n) for n in range(1,6)]
    print scores
    scores = [score for score in scores if score is not None]
    print scores
    t1wins = reduce(lambda total, val: (val[0] > val[1]) and total+1 or total, scores, 0)
    t2wins = reduce(lambda total, val: (val[1] > val[0]) and total+1 or total, scores, 0)
    points = toPoints(t1wins, t2wins)
    return {"id": match.id,
            "timestamp": match.timestamp,
            "player1": match.team1_player1.id,
            "player2": match.team2_player1.id,
            "scores": scores,
            "points": points,
            }


class SeedingSerializer(serializers.ModelSerializer):
  class Meta:
    model = Seeding
    fields = ["player", "seeding"]

class CompetitionSerializer(serializers.ModelSerializer):
  matches = CompactMatchField(source="match_set", many=True)
  seedings = SeedingSerializer(source="seeding_set", many=True)
  players = PlayerSerializer(many=True)
  class Meta:
    model = Competition
    depth = 0
    fields = ('id', 'name', 'end_date', 'url', 'players', 'seedings', 'matches')

  def __init__(self, *args, **kwargs):
    expanded = False
    if "expand" in kwargs:
      expanded = True
      del kwargs["expand"]
    elif "context" in kwargs:
      queryParams = kwargs["context"]["request"].GET
      expanded = "expand" in queryParams

    # Instantiate the superclass normally
    super(self.__class__, self).__init__(*args, **kwargs)

    if not expanded:
      self.fields.pop("matches")
      self.fields.pop("seedings")

class CompetitionGroupSerializer(serializers.ModelSerializer):
  matches = CompactMatchField(source="match_set", many=True)
  seedings = SeedingSerializer(source="seeding_set", many=True)
  players = PlayerSerializer(many=True)
  competitions_expanded = CompetitionSerializer(source="competitions", many=True, expand=True)
  class Meta:
    model = CompetitionGroup
    depth = 0
    fields = ('id', 'name', 'comp_type', 'end_date', 'active', 'competitions', 'competitions_expanded')

  def __init__(self, *args, **kwargs):
    # Instantiate the superclass normally
    super(self.__class__, self).__init__(*args, **kwargs)
    queryParams = kwargs["context"]["request"].GET
    if "expand" not in queryParams:
      self.fields.pop("competitions_expanded")
    else:
      self.fields.pop("competitions")

      
    
