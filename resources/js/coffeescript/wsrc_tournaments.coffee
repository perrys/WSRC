window.WSRC_tournaments =

  competition_data: null
  
  bind_tournament_events: () ->
    playerElts = jQuery("td.player").filter(":not(td.empty-match)")
    playerElts.mouseenter (evt) =>
      if  evt.target.innerHTML == "&nbsp;"
        return
      target = $(evt.target)
      matches = jQuery("td.player").filter(() -> $(this).data("teamid") == target.data("teamid"))
      matches.addClass(this.HIGHLIGHT_CLASS)
    playerElts.mouseleave (evt) =>      
      jQuery("td.#{ this.HIGHLIGHT_CLASS }").removeClass(this.HIGHLIGHT_CLASS)
    scoreDialog = (elt) =>
      tokens = elt.id.split("_")
      comp = tokens[1]
      matchId = parseInt(tokens[2])
      match = this.competitions[comp][matchId]
      this.showScoreEntryDialog([match])
      
    playerElts.filter(":not(td.partial-match)").dblclick (evt) ->
      scoreDialog(evt.target)
    playerElts.siblings().filter(".score").dblclick (evt) ->
      target = evt.target;
      while not target.classList.contains("player") # TODO - support older browsers
        target = target.previousSibling
      scoreDialog(target)

    return true
    
  refresh_tournament_data: (competition_data) ->
    this.competition_data = competition_data
    
    entrants = {}
    players = {}
    for p in competition_data.entrants
      entrants[p.player.id] = p
      players[p.player.id] = p.player
      if p.player2
        players[p.player2.id] = p.player2
    
    populateMatch = (match) ->
  
      # start with the html cells for the player names
      baseSelector = "td#match_#{ competition_data.id  }_#{ match.competition_match_id }"
      team1Elt = jQuery(baseSelector + "_t")  # top cell
      team2Elt = jQuery(baseSelector + "_b")  # bottom cell

      unless team1Elt.length and team2Elt.length
        return

      single_team = false
      if (not match.team1_player1) or (not match.team2_player1)
        single_team = true
        
      for elt in [team1Elt, team2Elt]
        elt.removeClass("empty-match")
        elt.nextUntil(".seed", ".score").removeClass("empty-match")
        elt.prev(".seed").removeClass("empty-match")
        if single_team
          elt.addClass("partial-match")
          elt.nextUntil(".seed", ".score").addClass("partial-match")
          elt.prev(".seed").addClass("partial-match")
  
      makeTeamName = (id1, id2) =>
        selector = (player) ->
          if id2
            return player.short_name 
          return player.full_name
        unless id1?
          return "&nbsp;"
        result = selector(players[id1])
        if id2
          result += " & " + selector(players[id2]) 
        return result.replace(" ", "&nbsp;")
        
      team1Name = makeTeamName(match.team1_player1, match.team1_player2) 
      team2Name = makeTeamName(match.team2_player1, match.team2_player2) 
      team1Elt.html(team1Name)
      team2Elt.html(team2Name)
      team1Elt.data("teamid", "#{ match.team1_player1 }_#{ match.team1_player2 }")
      team2Elt.data("teamid", "#{ match.team2_player1 }_#{ match.team2_player2 }")
  
      # now the seeds:
      addSeed = (id, elt) =>
        if id?
          entrant = entrants[id]
          if entrant.seeded
            elt.prev().html(entrant.ordering)
          else if entrant.handicap != null
            elt.prev().html(entrant.handicap + entrant.hcap_suffix)
      addSeed(match.team1_player1, team1Elt)
      addSeed(match.team2_player1, team2Elt)
  
      # if we have two players, add any scores avaialble:
      if match.team1_player1? and match.team2_player1?
        team1ScoreElt = team1Elt.next()
        team2ScoreElt = team2Elt.next()
        scores = match.scores
        if match.walkover?
          if match.walkover == 1
            team1Elt.addClass("winner")
            team2Elt.css("text-decoration", "line-through")
          else if match.walkover == 2
            team2Elt.addClass("winner")
            team1Elt.css("text-decoration", "line-through")
        else
          wins = [0,0]
          for [team1Score, team2Score] in scores
            if team1Score? and team2Score?
              team1ScoreElt.html(team1Score)
              team2ScoreElt.html(team2Score)
            else
              team1ScoreElt[0].innerHTML = "&nbsp;"
              team2ScoreElt[0].innerHTML = "&nbsp;"
            if team1Score > team2Score
              team1ScoreElt.addClass("winningscore")
              wins[0]++
            else if team1Score < team2Score
              team2ScoreElt.addClass("winningscore")
              wins[1]++
            team1ScoreElt = team1ScoreElt.next()
            team2ScoreElt = team2ScoreElt.next()
          if wins[0] > wins[1]
            team1Elt.addClass("winner")
          else if wins[0] < wins[1]
            team2Elt.addClass("winner")
      return true

    populateMatch(m) for m in competition_data.matches

    this.bind_tournament_events()
    
    return true
      
