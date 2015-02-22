
class WSRC_result_form

  # Handles interactions and maintains state for the result entry form. The form goes through a number of states:
  # 1. Teams unselected (first player drop-down contains teams from all valid matches)
  # 2. 1st Team selected. Second drop-down contains valid opponents for the first team selection
  # 3. Both teams selected - form is either in walkover state of score-entry state
  # 4a - walkover winner unselected
  # 4b - score-entry without at least one score populated
  # 5. Ready for submit 

  constructor: (@form, @competition_data, @valid_match_set, @selected_match, @team_type_prefix) ->

    unless @team_type_prefix
      @team_type_prefix = "Player"

    @players = WSRC_result_form.get_player_map(@competition_data.entrants)

    top_selector    = @form.find("select[name='team1']")
    bottom_selector = @form.find("select[name='team2']")

    @disable_and_reset_inputs(true)
    @fill_selector(top_selector, null)

    if selected_match
      wsrc.utils.select(top_selector,    selected_match.team1_player1)
      @handle_team1_selected(top_selector)
      wsrc.utils.select(bottom_selector, selected_match.team2_player1)
      @handle_team2_selected(bottom_selector)
    else
      if WSRC_user_player_id
        wsrc.utils.select(top_selector, WSRC_user_player_id)

  disable_and_reset_inputs: (include_team1_selector) ->
    @disable_score_entry()
    for i in [1, 2]
      empty_text = "#{ @team_type_prefix } #{ i }"
      @form.find("table.score-entry th.header-team#{ i }").text(empty_text)
      if i == 2 or include_team1_selector
        selector = @form.find("select[name='team#{ i }']")
        list = [["", empty_text]]
        wsrc.utils.fill_selector(selector, list)
        if i == 2
          selector.prop('disabled', true)
        selector.selectmenu('refresh')
    return null

  enable_score_entry: () ->
    @form.find("table.score-entry td input").textinput().textinput("enable")
    @form.find("table.score-entry tr").removeClass("wsrc-disabled")
    @form.find("input[type='radio']").checkboxradio().checkboxradio('enable')
    @form.find("button[type='button']").prop('disabled', false)
    return null
    
  disable_score_entry: () ->
    @form.find("table.score-entry td input").textinput().textinput("disable")
    @form.find("table.score-entry tr").addClass("wsrc-disabled")
    @form.find("input[name='result_type'][value='normal']").prop("checked",true).checkboxradio().checkboxradio("refresh")
    @form.find("input[name='result_type'][value='walkover']").prop("checked",false).checkboxradio().checkboxradio("refresh")
    @toggle_mode('normal')
    @form.find("input[type='radio']").checkboxradio().checkboxradio('disable')
    @form.find("button[type='button']").prop('disabled', true)
    return null
    

  toggle_mode: (mode) ->
    walkover = mode == "walkover"
    normal_elts = @form.find("table.score-entry")
    walkover_elts = @form.find("p.walkover-input")
    if walkover
      normal_elts.hide()
      walkover_elts.show()
    else
      normal_elts.show()
      walkover_elts.hide()
    
  # fill the given selector with team names, mapped to the team's
  # primary id. If OPPOSITION_ID_FILTER is provided, only
  # include matches with approrpriate opponents
  fill_selector: (selector, opposition_id_filter) ->
    teams = WSRC_result_form.get_team_map(@valid_match_set, @players, opposition_id_filter)
    team_list = WSRC_result_form.team_map_to_list(teams)
    name = selector[0].name
    suffix = name.substr(name.length-1)
    team_list.unshift(["", "#{ @team_type_prefix } #{ suffix }"])
    wsrc.utils.fill_selector(selector, team_list)
    return team_list[1..]

  handle_team1_selected: (selector) ->
    team1_id = WSRC_result_form.get_selected_id(selector)
    if team1_id
      teams = WSRC_result_form.get_team_map(@valid_match_set, @players)
      text = teams[team1_id].toString()
      @form.find("table.score-entry th.header-team1").text(text)
      bottom_selector = @form.find("select[name='team2']")
      bottom_selector.prop('disabled', false)
      team_list = @fill_selector(bottom_selector, team1_id)
      if team_list.length == 1
        wsrc.utils.select(bottom_selector, team_list[0][0])
        @handle_team2_selected(bottom_selector)
    else
      @disable_and_reset_inputs(false)
    
  handle_team2_selected: (selector) ->
    team2_id = WSRC_result_form.get_selected_id(selector)
    if team2_id
      teams = WSRC_result_form.get_team_map(@valid_match_set, @players)
      text = teams[team2_id].toString()
      @form.find("table.score-entry th.header-team2").text(text)
      top_selector = @form.find("select[name='team1']")
      team1_id = WSRC_result_form.get_selected_id(top_selector)
      if team1_id
        @enable_score_entry()
        list = [
          ["", "Winner"]
          [team1_id, teams[team1_id].toString()]
          [team2_id, teams[team2_id].toString()]
        ]
        walkover_selector = @form.find("select[name='walkover_result']")
        wsrc.utils.fill_selector(walkover_selector, list)
    else
      @disable_score_entry()

  handle_result_type_changed: (input) ->
    @toggle_mode(input.value)
    # call the change handlers to invalidate the submit button if necessary
    if input.value == 'walkover'
      walkover_selector = @form.find("select[name='walkover_result']")
      @handle_walkover_result_changed(walkover_selector)
    else
      @handle_score_changed()
    return null

  handle_walkover_result_changed: (selector) ->
    valid = $(selector).val().length > 0
    @form.find("button[type='submit']").prop('disabled', not valid)
    return null

  handle_score_changed: () ->
    valid = @validate_scores()
    @form.find("button[type='submit']").prop('disabled', not valid)
    return null
    
  # check that the entered scores are a valid match result. We need at
  # least one valid set result. Multiple sets cannot contain blank
  # rows.
  validate_scores: () ->
    total = 0
    blank_row_found = false    
    for i in [1..5]
      val1 = @form.find("input[name='team1_score#{ i }']").val()
      val2 = @form.find("input[name='team2_score#{ i }']").val()
      if val1.length > 0 or val2.length > 0
        if blank_row_found
          return false
        # use absolute values as handicap scores can be negative, and
        # e.g. -15/15 is a valid result
        row_total = Math.abs(parseInt(val1)) + Math.abs(parseInt(val2))
        if isNaN(row_total) or row_total == 0
          return false
        total += row_total
      else
        blank_row_found = true
    return not isNaN(total) and total > 0
                
  # return a map of players in the comp keyed by their player id
  @get_player_map: (entrants) ->
    players = {}
    for e in entrants
      players[e.player.id] = e.player
      if e.player2
        players[e.player2.id] = e.player2
    return players
    
  # return a map of teams keyed by the first player's id. Each team
  # object has "player" and "player2" properties. If
  # OPPOSITION_ID_FILTER is provided, only include matches with
  # this opponent team, and do not include that team in the returned list
  @get_team_map: (match_set, players, opposition_id_filter) ->
    teams = {}
    filter = (match) ->
      if opposition_id_filter
        return match.team1_player1 == opposition_id_filter or
          match.team1_player2 == opposition_id_filter or
          match.team2_player1 == opposition_id_filter or
          match.team2_player2 == opposition_id_filter
      return true
    for match in match_set
      if filter(match)
        for i in [1,2]
          player1_id = match["team#{ i }_player1"]
          player2_id = match["team#{ i }_player2"]
          if opposition_id_filter
            if player1_id == opposition_id_filter or player2_id == opposition_id_filter
              continue
          team = new WSRC_team(players[player1_id], players[player2_id])
          teams[team.primary_id] = team
    return teams

  @team_map_to_list: (team_map) ->
    team_list = (t for id, t of team_map)
    team_list.sort (lhs,rhs) ->
      (lhs.toString() > rhs.toString()) - (lhs.toString() < rhs.toString())
    team_list = ([p.primary_id, p.toString()] for p in team_list)
    return team_list

  @get_selected_id: (selector) ->
    selected_value = $(selector).val()
    if selected_value.length > 0
      selected_value = parseInt(selected_value)
    else
      selected_value = null
    return selected_value

  @get_controler: (form) ->
    $(form).data("controller") # get the instance of this class associted with the form
    
  # static method bound to the team selectors in the form.        
  @on_team_selected: (selector) ->
    form_controller = WSRC_result_form.get_controler(selector.form)
    if selector.name == "team1"
      form_controller.handle_team1_selected(selector)
    else if selector.name == "team2"
      form_controller.handle_team2_selected(selector)

  @on_result_type_changed: (input) ->
    form_controller = WSRC_result_form.get_controler(input.form)
    form_controller.handle_result_type_changed(input)

  @on_walkover_result_changed: (selector) ->
    form_controller = WSRC_result_form.get_controler(selector.form)
    form_controller.handle_walkover_result_changed(selector)

  @on_score_changed: (input) ->
    form_controller = WSRC_result_form.get_controler(input.form)
    form_controller.handle_score_changed()

  load_scores_for_match: (cfg, players) ->
    existing_match = null
    p1idx = 0
    p2idx = 1
    if players?
      for match in cfg.matches
        if players[0] == match.team1_player1 and players[1] == match.team2_player1
          existing_match = match
          break
        else if players[0] == match.team2_player1 and players[1] == match.team1_player1
          existing_match = match
          p1idx = 1
          p2idx = 0
          break
    form = jQuery("form#add-change-form")
    match_id_field = form.find("input#match_id")
    idx = 1
    if not existing_match?
      match_id_field.val("")
    else
      match_id_field.val(existing_match.id)
      for s in existing_match.scores
        form.find("input#team1_score#{ idx }").val(s[p1idx])
        form.find("input#team2_score#{ idx }").val(s[p2idx])
        idx += 1
      radios = form.find("input[name='result_type']")
      if existing_match.walkover?
        radios.filter("[value='walkover']").prop("checked", true)
        radios.checkboxradio("refresh")
        this.result_type_changed()
        winner_select = form.find("select#walkover_result")
        if existing_match.walkover == 1
          winner_select.val(match.team1_player1)
        else
          winner_select.val(match.team2_player1)
        winner_select.selectmenu("refresh")
      else
        radios.filter("[value='normal']").prop("checked", true)
        radios.checkboxradio("refresh")
        this.result_type_changed()
        
    while idx <=5
      form.find("input#team1_score#{ idx }").val("")
      form.find("input#team2_score#{ idx }").val("")
      idx += 1

    if existing_match?
      this.validate_match_result()


  submit_match_result: () ->
    box_id = parseInt(jQuery("input#competition_id").val())
    this_box_config = this.get_competition_for_id(box_id)
    form = jQuery("form#add-change-form")
    selects = (form.find("select##{ p }") for p in ['player1', 'player2'])
    player_ids = (parseInt(e.val()) for e in selects)
    match_id_field = form.find("input#match_id")
    csrf_token = form.find("input[name='csrfmiddlewaretoken']").val()
    data = {
      competition: box_id,
      team1_player1: player_ids[0],
      team2_player1: player_ids[1]
    }
    for i in [1..5]
      for j in [1..2]
        score = form.find("input#team#{ j }_score#{ i }").val()
        if wsrc.utils.is_valid_int(score)
          data["team#{ j }_score#{ i }"] = parseInt(score)
    match_id = match_id_field.val()
    result_type = form.find("input[name='result_type']:checked").val()
    if result_type == "walkover"
      winner_id = parseInt(form.find("select#walkover_result").val())
      if winner_id == player_ids[0]
        data.walkover = 1
      else
        data.walkover = 2
    if wsrc.utils.is_valid_int(match_id) 
      # update existing match result:
      data.id = parseInt(match_id)
      url = "/data/match/#{ match_id }"
      wsrc.ajax.PUT(url, data,
        successCB: (data) =>
          return true
        failureCB: (xhr, status) => 
          this.show_error_dialog("ERROR: Failed to load data from #{ url }")
          return false
        csrf_token: csrf_token
      )
    else
      # new match result:
      url = "/data/match/"
      wsrc.ajax.POST(url, data,
        successCB: (data) =>
          return true
        failureCB: (xhr, status) => 
          this.show_error_dialog("ERROR: Failed to load data from #{ url }")
          return false
        csrf_token: csrf_token
      )

    return false
    
window.WSRC_result_form = WSRC_result_form
