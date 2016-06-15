class WSRC_Tournament

  @HIGHLIGHT_CLASS: "wsrc-highlight"
    
  constructor: (@competition_data, @page_dirty_callback) ->
    @refresh_tournament(@competition_data)

  refresh_tournament: () ->
    WSRC_Tournament.populate_matches(@competition_data)
    @bind_tournament_events()
    
  show_score_entry_dialog: (permitted_matches, selected_match) ->
    dialog = $('#score_entry_dialog')
    form = dialog.find("form.match-result-form")
    prefix = if @competition_data.name.indexOf("Doubles") >= 0 then "Team" else "Player"
    submit_callback = () =>
      dialog.popup("close")
      if @page_dirty_callback
        @page_dirty_callback()
    form_controller = new wsrc.result_form(form, @competition_data, permitted_matches, selected_match, prefix, submit_callback)
    form.data("controller", form_controller)
    dialog.popup('open')

  get_unplayed_matches: () ->
    predicate = (match) ->
      unless match.team1 and match.team2
        return false
      if match.scores.length > 0
        return false # todo - allow authorized users to edit existing matches
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
        return myteam == theirteam
      matches.addClass(wsrc.Tournament.HIGHLIGHT_CLASS)
    playerElts.mouseleave (evt) =>      
      jQuery("td.#{ wsrc.Tournament.HIGHLIGHT_CLASS }").removeClass(wsrc.Tournament.HIGHLIGHT_CLASS)

    unless WSRC_is_authenticated?
      return null
      
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

    return null

  @on_edit_clicked: (button) ->
    page = $(button).parents("div[data-role='page']")
    controller = page.data("tournament")
    matches = controller.get_unplayed_matches()
    controller.show_score_entry_dialog(matches)
    
  @populate_matches: (competition_data) ->
    
    entrants = {}
    for entrant in competition_data.entrants
      entrants[entrant.id] = entrant
    
    populateMatch = (match) ->
  
      # start with the html cells for the player names
      baseSelector = "td#match_#{ competition_data.id  }_#{ match.competition_match_id }"
      team1Elt = jQuery(baseSelector + "_t")  # top cell
      team2Elt = jQuery(baseSelector + "_b")  # bottom cell
      team1 = entrants[match.team1]
      team2 = entrants[match.team2]

      unless team1Elt.length and team2Elt.length
        return

      single_team = false
      if (not team1?.player1) or (not team2?.player1)
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

      set_team = (elt, idx) ->
        team_id = match["team#{ idx }"]
        if team_id
          elt.html(entrants[team_id].name)
          elt.data("team", team_id)
      for [elt, idx] in [[team1Elt, 1], [team2Elt, 2]]
        set_team(elt, idx)
  
      # now the seeds:
      addSeed = (id, elt) =>
        if id?
          entrant = entrants[id]
          if entrant.seeded
            elt.prev().html(entrant.ordering)
          else if entrant.handicap != null
            elt.prev().html(entrant.handicap + entrant.hcap_suffix)
      addSeed(match.team1, team1Elt)
      addSeed(match.team2, team2Elt)
  
      # if we have two players, add any scores avaialble:
      if match.team1? and match.team2?
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

    $("td.partial-match").removeClass("partial-match")
    $("td.completed-match").removeClass("completed-match")
    populateMatch(m) for m in competition_data.matches

    return true
      
wsrc.utils.add_to_namespace("Tournament", WSRC_Tournament)
