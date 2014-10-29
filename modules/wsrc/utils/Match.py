


class Match:

  # row should be id, tournament_id, round, lastEmail, previous, <team details>, deadline, score1, score2
  def __init__(self, row):

    self.id            = row[0]; row = row[1:]
    self.tournament_id = row[0]; row = row[1:]

    self.team1 = []
    self.team2 = []
    self.scores = [None, None]

    self.lastEmail = None
    self.previous  = None

    if len(row) > 0:
      self.round         = row[0]; row = row[1:]
      self.lastEmail     = row[0]; row = row[1:]
      self.previous      = row[0]; row = row[1:]
      if row[0] is not None:
        self.team1.append(row[0])
        if row[1] is not None:
          self.team1.append(row[1])
      if row[2] is not None:
        self.team2.append(row[2])
        if row[3] is not None:
          self.team2.append(row[3])
      row = row[4:]
      if len(row) > 0:
        self.deadline = row[0]; row = row[1:]
      if len(row) > 1:
        self.scores[0] = row[0]
        self.scores[1] = row[1]
        row = row[2:]


  def __eq__(self, other):
    result = self.id == other.id \
        and self.tournament_id == other.tournament_id \
        and self.team1 == other.team1 \
        and self.team2 == other.team2 \
        and self.scores == other.scores
    if not result:
      print result, self.id, other.id, self.team1, other.team1, self.team2, other.team2, self.scores, other.scores
    return result

  def __ne__(self, other):
    return not self.__eq__(other)

  def describeDiff(self, other, userMap):
    buf = ""
    def describe(attrib, translate=False):
      val = self.__dict__[attrib]
      if translate:
        val = [userMap[k] for k in val]
      return "%s: %s " % (attrib, val)
    if len(other.team1) == 0 and len(self.team1) > 0 :
      buf += describe("team1", True)
    if len(other.team2) == 0 and len(self.team2) > 0:
      buf += describe("team2", True)
    if self.scores[0] is not None:
      buf += describe("scores")
    return buf

  def addPlayerOrPlayersToTeam(self, team, playerOrPlayers, nameToIdConverter, score):
    teamList = self.team1
    if team == 2:
      teamList = self.team2
    users = playerOrPlayers.split(" & ")
    teamList.append(nameToIdConverter(users[0]))
    if len(users) > 1:
      teamList.append(nameToIdConverter(users[1]))
    if score is not None:
      self.scores[team-1] = score
      
    
