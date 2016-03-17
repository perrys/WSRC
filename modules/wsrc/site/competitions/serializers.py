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
from wsrc.site.competitions.models import CompetitionGroup, Competition, Match, Entrant, CompetitionRound

SCORE_TO_POINTS_MAPPING = {3 : {0: (7,2), 1: (6,3), 2: (5,4)},
                           2 : {0: (4,2), 1: (4,3), 2: (4,4)},
                           1 : {0: (3,2), 1: (3,3)},
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

class EntrantSerializer(serializers.ModelSerializer):
  player = PlayerSerializer(required=True)
  player2 = PlayerSerializer(required=False)
  class Meta:
    model = Entrant
    fields = ('player', 'player2', 'ordering', "seeded", "handicap", "hcap_suffix")

class EntrantDeSerializer(serializers.ModelSerializer):
  class Meta:
    model = Entrant
    fields = ('competition', 'player', 'player2', 'ordering', "seeded", "handicap", "hcap_suffix")
  def create(self, validated_data):
      return Entrant.objects.create(**validated_data)

class RoundSerializer(serializers.ModelSerializer):
  class Meta:
    model = CompetitionRound
    fields = ('round', 'end_date')

class MatchSerializer(serializers.ModelSerializer):
  class Meta:
    model = Match

class StatusField(serializers.CharField):
  def to_representation(self, comp_group):
    for comp in comp_group.all():
        return comp.state
    return 'empty'

class CompactMatchField(serializers.RelatedField):
  def to_representation(self, match):
    scores = match.get_scores()
    if match.walkover is not None:
      points = (match.walkover == 1) and [7,2] or [2,7]
    else:
      sets_won = match.get_sets_won(scores)
      points = toPoints(min(sets_won[0],3), min(sets_won[1],3))
    def safe_get_id(attr):
        player = getattr(match, attr)
        if player is not None:
            return player.id
        return None
    return {"id": match.id,
            "competition_match_id": match.competition_match_id,
            "last_updated": match.last_updated,
            "team1_player1": safe_get_id("team1_player1"),
            "team2_player1": safe_get_id("team2_player1"),
            "team1_player2": safe_get_id("team1_player2"),
            "team2_player2": safe_get_id("team2_player2"),
            "scores": scores,
            "points": points,
            "walkover": match.walkover,
            }


class CompetitionSerializer(serializers.ModelSerializer):
  matches = CompactMatchField(source="match_set", many=True, read_only=True)
  entrants = EntrantSerializer(source="entrant_set", many=True)
  rounds   = RoundSerializer(many=True, required=False)
  class Meta:
    model = Competition
    depth = 0
    fields = ('id', 'name', 'end_date', 'ordering', 'group', 'state', 'url', 'entrants', 'matches', 'rounds')

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
  
  def update_entrants(self, instance, entrants):
    for e in instance.entrant_set.all():
        e.delete()
    for e in entrants:
      e["competition"] = instance.id
      e["player"] = e["player"]["id"]
      e["player2"] = e.get("player2") and e["player2"]["id"] or None
      serializer = EntrantDeSerializer(data=e)        
      if not serializer.is_valid():
        raise Exception(serializer.errors)
      serializer.save()

  def create(self, validated_data):
    validated_data.pop("entrant_set")
    instance = self.Meta.model.objects.create(**validated_data)
    self.update_entrants(instance, self.initial_data["entrants"])
    return instance

  def update(self, instance, validated_data):
    validated_data.pop("entrant_set")
    for attr, value in validated_data.items():
      setattr(instance, attr, value)
    instance.save()
    self.update_entrants(instance, self.initial_data["entrants"])
    return instance

class CompetitionGroupSerializer(serializers.ModelSerializer):
  competitions_expanded = CompetitionSerializer(source="competition_set", many=True, expand=True, read_only=True)
  status   = StatusField(source="competition_set", read_only=True)
  class Meta:
    model = CompetitionGroup
    depth = 0
    fields = ('id', 'name', 'comp_type', 'end_date', 'active', 'competition_set', 'competitions_expanded', 'status')

  def __init__(self, *args, **kwargs):
    # Instantiate the superclass normally
    super(self.__class__, self).__init__(*args, **kwargs)
    queryParams = {}
    if "context" in kwargs:
      queryParams = kwargs["context"]["request"].GET
    if "expand" not in queryParams:
      self.fields.pop("competitions_expanded")
    else:
      self.fields.pop("competition_set")

  def update_competitions(self, instance, competition_set):
    for e in instance.competition_set.all():
        e.delete()
    for comp in competition_set:
      comp["group"] = instance.id
      serializer = CompetitionSerializer(data=comp)        
      if not serializer.is_valid():
        raise Exception(serializer.errors)
      serializer.save()


  def create(self, validated_data):
    competition_set = self.initial_data.pop("competitions_expanded")
    instance = self.Meta.model.objects.create(**validated_data)
    instance.save()
    self.update_competitions(instance, competition_set)
    return instance

  def update(self, instance, validated_data):
    print validated_data
    print self.initial_data
    competition_set = self.initial_data.pop("competitions_expanded")
    for attr, value in validated_data.items():
      setattr(instance, attr, value)
    instance.save()
    self.update_competitions(instance, competition_set)
    return instance
      
# Local Variables:
# mode: python
# python-indent-offset: 2
# End:
