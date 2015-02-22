class WSRC_Tournament

  @HIGHLIGHT_CLASS: "wsrc-highlight"
    
  constructor: (@competition_data) ->
    @refresh_tournament(@competition_data)

  refresh_tournament: () ->
    WSRC_Tournament.populate_matches(@competition_data)
    @bind_tournament_events()
    
  show_score_entry_dialog: (permitted_matches, selected_match) ->
    dialog = $('#score_entry_dialog')
    form = dialog.find("form.match-result-form")
    prefix = if @competition_data.name.indexOf("Doubles") >= 0 then "Team" else "Player"
    form_controller = new wsrc.result_form(form, @competition_data, permitted_matches, selected_match, prefix)
    form.data("controller", form_controller)
    dialog.popup('open')

  get_unplayed_matches: () ->
    predicate = (match) ->
      if match.scores.length > 0
        return false
      unless match.team1_player1 and match.team2_player1
        return false
      return true
    matches = (m for m in this.competition_data.matches when predicate(m))
    return matches
    
  bind_tournament_events: () ->
    playerElts = jQuery("td.player")
    playerElts.unbind()
    
    playerElts = playerElts.filter(":not(td.empty-match)")
    playerElts.mouseenter (evt) =>
      target = $(evt.target)
      myteam = target.data("team")
      unless myteam
        return false
      matches = jQuery("td.player").filter () ->
        theirteam = $(this).data("team")
        unless theirteam
          return false
        return myteam.primary_id == theirteam.primary_id
      matches.addClass(wsrc.Tournament.HIGHLIGHT_CLASS)
    playerElts.mouseleave (evt) =>      
      jQuery("td.#{ wsrc.Tournament.HIGHLIGHT_CLASS }").removeClass(wsrc.Tournament.HIGHLIGHT_CLASS)
      
    open_score_entry_dialog = (elt) =>
      tokens = elt.id.split("_")
      comp = tokens[1]
      matchId = parseInt(tokens[2])
      matches = $.grep(this.competition_data.matches, (obj, idx) ->
        obj.competition_match_id == matchId
      )
      if matches.length != 1
        throw "ERROR: expected 1 match for id #{ matchId }, got #{ matches.length }"
      this.show_score_entry_dialog(this.get_unplayed_matches(), matches[0])
      
    playerElts = playerElts.filter(":not(td.partial-match)")
    playerElts = playerElts.filter(":not(td.completed-match)")

    playerElts.dblclick (evt) ->
      open_score_entry_dialog(evt.target)
    playerElts.on "taphold", (evt) ->
      open_score_entry_dialog(evt.target)
    
    playerElts.siblings().filter(".score").dblclick (evt) ->
      target = evt.target;
      while not target.classList.contains("player") # TODO - support older browsers
        target = target.previousSibling
      open_score_entry_dialog(target)

    return true
    
  @populate_matches: (competition_data) ->
    
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
        apply_to_row = (f) ->
          f elt
          f elt.nextUntil(".seed", ".score")
          f elt.prev(".seed")
        apply_to_row (target) -> target.removeClass("empty-match")
        if single_team
          apply_to_row (target) -> target.addClass("partial-match")
        else if match.scores.length > 0
          apply_to_row (target) -> target.addClass("completed-match")
  
      team1 = new WSRC_team(players[match.team1_player1], players[match.team1_player2])
      team2 = new WSRC_team(players[match.team2_player1], players[match.team2_player2])
      team1Elt.html(team1.toString())
      team2Elt.html(team2.toString())
      team1Elt.data("team", team1)
      team2Elt.data("team", team2)
  
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

    return true
      
wsrc.utils.add_to_namespace("Tournament", WSRC_Tournament)