#!/usr/bin/python

import sys
import os.path
import flask
import httplib
import datetime
import hashlib

app = flask.Flask(__name__)

import logging

sys.path.append(os.path.dirname(__file__) + "/lib")
from Database import DataBase

AUTH_USER = "wsrc2014"
AUTH_TOKEN = hashlib.md5("1945").hexdigest()

def plain_response(msg, status):
  return flask.make_response(msg, status, {"Content-Type": "text/plain"})

def safeint(v):
  if v is None: return None
  return int(v)

def get_matches(tournament_id, match_id = None):
  params = [tournament_id]
  sql = "select Match_Id"
  for team in [1, 2]:
    for player in [1, 2]:
      sql += ", Team%(team)d_Player%(player)d_Id" % locals()
    for score in range (1,6):
      sql += ", Team%(team)d_Score%(score)d"  % locals()
  sql += " from TournamentMatch where Tournament_Id = %s"
  if match_id is not None:
    sql += " and Match_Id = %s"
    params.append(match_id)
  dbh = DataBase()
  data,fields = dbh.queryAndStore(sql, params, True)
  result = dict([(row[0], dict([(fields[i], row[i]) for i in range(1, len(row))])) for row in data])
  return result


@app.route("/players")
def get_players():
  dbh = DataBase()
  users = dbh.queryAndStore("select Id, Name, ShortName from User")
  result = dict([(u[0], {"name": u[1], "shortname": u[2], "seeding": {}}) for u in users])
  seeds = dbh.queryAndStore("select User_Id, Tournament_Id, Seed from Seed")
  for row in seeds:
    seeding = result[row[0]]["seeding"]
    seeding[row[1]] = row[2]
  return flask.json.jsonify(payload=result)

@app.route("/tournament")
def get_tournament():
  dbh = DataBase()
  year = flask.request.args.get("year")
  if year is None:
    year = datetime.date.today().year
  sql = "select T.Id, T.Name, TR.Round, TR.CloseDate from Tournament T, TournamentRound TR where T.Id = TR.Tournament_Id and T.Year = %s"
  data = dbh.queryAndStore(sql, [year])
  result = dict()
  for row in data:
    comp = result.get(row[0])
    if comp is None:
      comp = {"name": row[1], "nRounds": 0, "rounds": {}}
      result[row[0]] = comp
    rounds = comp["rounds"]
    comp["nRounds"] += 1
    rounds[row[2]] = row[3].isoformat()
  for comp in result.itervalues():
    d = dict()
    nRounds = comp["nRounds"]
    for k,v in comp["rounds"].iteritems():
      d[nRounds-k] = v
    comp["rounds"] = d
  return flask.json.jsonify(payload=result)

@app.route("/competition")
def get_competition():
  tournament_id = flask.request.args.get("id")
  result = get_matches(tournament_id)
  return flask.json.jsonify(payload=result)

@app.route("/match", methods=['GET', 'POST', 'DELETE'])
def get_or_update_match():

  request_args = flask.request.values

  try:
    tournament_id = int(request_args.get("tournament_id"))
    match_id      = int(request_args.get("match_id"))
  except TypeError, e:
    return plain_response("Must supply valid tournament_id and match_id", httplib.BAD_REQUEST)

  match = get_matches(tournament_id, match_id)
  if len(match) != 1:
      return plain_response("Cannot find match (%(match_id)d, %(tournament_id)d)" % locals(), httplib.NOT_FOUND)

  match = match[match_id]

  if flask.request.method == 'GET':
    return flask.json.jsonify(payload=match)

  else:
    # request to update or delete a match score
    login_id    = request_args.get("login_id")
    login_token = request_args.get("login_token")

    if (not login_id) or (not login_token):
      return plain_response("Authentication Failed", httplib.UNAUTHORIZED)
    if (login_id != AUTH_USER) or (login_token != AUTH_TOKEN): 
      return plain_response("User \"%(login_id)s\" cannot change match (%(match_id)d, %(tournament_id)d)" % locals(), httplib.FORBIDDEN)

    try:
      player1_id = safeint(request_args.get("player1_id"))
      player2_id = safeint(request_args.get("player2_id"))
    except TypeError, e:
      return plain_response("Must supply valid player ids", httplib.BAD_REQUEST)

    if player1_id != match["Team1_Player1_Id"] or player2_id != match["Team2_Player1_Id"]:
      return plain_response("Inconsistent players for (%(match_id)d, %(tournament_id)d)" % locals(), httplib.CONFLICT)

    # the next match id is simply the right-shift of the current one, due to the binomial id scheme
    next_match_id = match_id>>1
    next_match = get_matches(tournament_id, next_match_id)
    if len(next_match) == 1: # next match may or may not already exist in the database
      next_match = next_match[next_match_id]
    else:
      next_match = None

    # first, we handle delete requests
    if flask.request.method == 'DELETE':
      if next_match is not None:
        return plain_response("Cannot delete (%(match_id)d, %(tournament_id)d) as later match exists" % locals(), httplib.CONFLICT)
      sql = "DELETE from TournamentMatch where Match_Id = %s and Tournament_Id = %s"
      params = [match_id, tournament_id]
      DataBase().update(sql, params)
      return plain_response("", httplib.RESET_CONTENT)
      
    # at this point the request must be for an update to an existing match

    # first check if it was a walkover; we use the convention of the losing player scoring -1
    walkover_result = safeint(request_args.get("walkover_result"))
    if walkover_result is not None:
      if walkover_result == player1_id:
        scores = [(0,-1)]
      elif walkover_result == player2_id:
        scores = [(-1,0)]
      else:
        return plain_response("Walkover result not consistent with match players for (%(match_id)d, %(tournament_id)d)" % locals(), 
                              httplib.CONFLICT)
    else: # not a walkover so get the real scores
      def getScores(player):
        scores = [request_args.get("team%(player)d_score%(i)d" % locals()) for i in range(1,6)]
        return [safeint(score) for score in scores]
      scores = zip(getScores(1), getScores(2))

    # check that we have a winner:
    wins = [0,0]
    for (score1, score2) in scores:
      if score1 > score2:
        wins[0] += 1
      elif score2 > score1:
        wins[1] += 1
    if wins[0] == wins[1]:
      return plain_response("Cannot submit a draw, must have a winner, %(scores)s" % locals(), 
                            httplib.BAD_REQUEST)
    winner = wins[0] > wins[1] and player1_id or player2_id

    # Check next match, create or udpate as necessary:
    def getNextPlayerColumn():
      isFirst = 0 == (match_id & 0x1)
      return (isFirst and "Team1_Player1_Id" or "Team2_Player1_Id") + " = %s"

    if next_match is not None:
      isFirst = 0 == (match_id & 0x1)
      nextPlayer = isFirst and next_match["Team1_Player1_Id"] or next_match["Team2_Player1_Id"]
      if nextPlayer is not None and nextPlayer != winner and next_match.get("Team1_Score1") is not None:
        return plain_response("Changing this resuult conflicts with next round match already played", httplib.CONFLICT)
      sql = "UPDATE TournamentMatch SET Last_Update = NOW(), "
      sql += getNextPlayerColumn()
      sql += " WHERE Match_Id = %s and Tournament_Id = %s"
      DataBase().update(sql, [winner, next_match_id, tournament_id])
    else:
      sql = "INSERT INTO TournamentMatch SET Match_id = %s, Tournament_Id = %s, Last_Update = NOW(), "
      sql += getNextPlayerColumn()
      DataBase().update(sql, [next_match_id, tournament_id, winner])
      
    # now update the result for this match:
    sql = "UPDATE TournamentMatch SET"
    params = []
    for i in range(0, 5):
      (score1, score2) = (None, None)
      if i < len(scores):
        (score1, score2) = scores[i]
        if score1 == score2 == 0:
          (score1, score2) = (None, None)
      setnumber = i + 1
      if setnumber > 1: 
        sql += ", "
      sql += "  Team1_Score%(setnumber)d" % locals() + " = %s" 
      sql += ", Team2_Score%(setnumber)d" % locals() + " = %s"
      params.append(score1)
      params.append(score2)
    sql += " WHERE Match_Id = %s and Tournament_Id = %s and Team1_Player1_Id = %s and Team2_Player1_Id = %s"
    params.extend((match_id, tournament_id, player1_id, player2_id))

    DataBase().update(sql, params)
    return plain_response("", httplib.RESET_CONTENT)
    
if __name__ == "__main__":
  app.logger.addHandler(logging.StreamHandler(sys.stderr))
  app.logger.setLevel(logging.DEBUG)
  app.run(debug=True,  host='0.0.0.0')
