from django.db import models

import wsrc.site.usermodel.models

# Create your models here.

class Team(models.Model):  
  player1 = models.ForeignKey(wsrc.site.usermodel.models.Player, related_name="team_p1+")
  player2 = models.ForeignKey(wsrc.site.usermodel.models.Player, related_name="team_p2+", null=True)

class Competition(models.Model):
  name = models.CharField(max_length=128)
  end_date = models.DateField()
  teams = models.ManyToManyField(Team)

class Match(models.Model):
  competition = models.ForeignKey(Competition)
  competition_match_id = models.CharField(max_length=32, help_text="Unique ID of this match within its competition")
  team1 = models.ForeignKey(Team, related_name="match_2+", null=True)
  team2 = models.ForeignKey(Team, related_name="match_2+", null=True)
  team1_score1 = models.IntegerField(null=True)
  team1_score2 = models.IntegerField(null=True)
  team1_score3 = models.IntegerField(null=True)
  team1_score4 = models.IntegerField(null=True)
  team1_score5 = models.IntegerField(null=True)
  team2_score1 = models.IntegerField(null=True)
  team2_score2 = models.IntegerField(null=True)
  team2_score3 = models.IntegerField(null=True)
  team2_score4 = models.IntegerField(null=True)
  team2_score5 = models.IntegerField(null=True)
  deadline = models.DateField(null=True)
    
class LeagueSet(models.Model):
  boxes = models.ManyToManyField(Competition)
  end_date = models.DateField()
  
