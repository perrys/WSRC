
class WSRC_result_form

  # Handles interactions and maintains state for the result entry form. The form goes through a number of states:
  # 1. Teams unselected (first player drop-down contains teams from all valid matches)
  # 2. 1st Team selected. Second drop-down contains valid opponents for the first team selection
  # 3. Both teams selected - form is either in walkover state of score-entry state
  # 4a - walkover winner unselected
  # 4b - score-entry without at least one score populated
  # 5. Ready for submit 

  constructor: (@form, @competition_data, @valid_match_set, @selected_match, @team_type_prefix, @submitted_callback) ->

    unless @team_type_prefix
      @team_type_prefix = "Player"

    @entrants_map = wsrc.utils.list_to_map(@competition_data.entrants, "id")
    @players = WSRC_result_form.get_player_map(@competition_data.entrants)

    top_selector    = @form.find("select[name='team1']")
    bottom_selector = @form.find("select[name='team2']")

    @disable_and_reset_inputs(true)
    @fill_selector(top_selector, null)

    if selected_match
      wsrc.utils.select(top_selector,    selected_match.team1)
      @handle_team1_selected(top_selector)
      wsrc.utils.select(bottom_selector, selected_match.team2)
      @handle_team2_selected(bottom_selector)
      @load_scores_for_match(selected_match, false)
    else
      if WSRC_user_player_id
        wsrc.utils.select(top_selector, WSRC_user_player_id)
        @handle_team1_selected(top_selector)

    @form.find(".score-row :input").on("focusout", (event) =>
      @handle_score_changed()
    )

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
    for idx in [1..5]
      @form.find(":input[name='team1_score#{ idx }']").val("")
      @form.find(":input[name='team2_score#{ idx }']").val("")
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
    entrants = WSRC_result_form.get_entrant_map(@valid_match_set, @entrants_map, opposition_id_filter)
    entrant_tuples = WSRC_result_form.entrant_map_to_tuples(entrants)
    name = selector[0].name
    suffix = name.substr(name.length-1)
    entrant_tuples.unshift(["", "#{ @team_type_prefix } #{ suffix }"])
    wsrc.utils.fill_selector(selector, entrant_tuples)
    return entrant_tuples[1..]

  handle_team1_selected: (selector) ->
    team1_id = WSRC_result_form.get_selected_id(selector)
    if team1_id
      text = @entrants_map[team1_id].name
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
      text = @entrants_map[team2_id].name
      @form.find("table.score-entry th.header-team2").text(text)
      top_selector = @form.find("select[name='team1']")
      team1_id = WSRC_result_form.get_selected_id(top_selector)
      if team1_id
        @enable_score_entry()
        list = [
          ["", "Winner"]
          [team1_id, @entrants_map[team1_id].name]
          [team2_id, @entrants_map[team2_id].name]
        ]
        walkover_selector = @form.find("select[name='walkover_result']")
        wsrc.utils.fill_selector(walkover_selector, list)
    else
      @disable_score_entry()
    @load_scores_for_match()

  set_result_type: (type) ->
    radios = @form.find("input[name='result_type']")
    radio = radios.filter("[value='#{ type }']")
    radio.prop("checked", true)
    radios.checkboxradio("refresh")
    @handle_result_type_changed(radio[0])
    return null
    
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
      val1 = @form.find(":input[name='team1_score#{ i }']").val() or ""
      val2 = @form.find(":input[name='team2_score#{ i }']").val() or ""
      if val1.length > 0 or val2.length > 0
        if blank_row_found
          return false
        # use absolute values as handicap scores can be negative, and
        # e.g. -15/15 is a valid result
        row_total = Math.abs(wsrc.utils.to_int(val1)) + Math.abs(wsrc.utils.to_int(val2))
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
      players[e.player1.id] = e.player
      if e.player2
        players[e.player2.id] = e.player2
    return players
    
  # return a map of teams keyed by the first player's id. Each team
  # object has "player" and "player2" properties. If
  # OPPOSITION_ENTRANT_ID is provided, only include matches with
  # this opponent team, and do not include that team in the returned list
  @get_entrant_map: (match_set, entrant_map, opposition_entrant_id) ->
    result = {}
    filter = (match) ->
      if opposition_entrant_id
        return match.team1 == opposition_entrant_id or
          match.team2 == opposition_entrant_id
      return true
    for match in match_set
      if filter(match)
        for i in [1,2]
          entrant_id = match["team#{ i }"]
          if opposition_entrant_id
            if entrant_id == opposition_entrant_id
              continue
          result[entrant_id] = entrant_map[entrant_id]
    return result

  @entrant_map_to_tuples: (entrant_map) ->
    entrant_list = ([id, t.name] for id, t of entrant_map)
    mapper = (tup) -> tup[1]
    entrant_list.sort (l,r) -> wsrc.utils.lexical_sorter(l, r, mapper)
    return entrant_list

  @get_selected_id: (selector) ->
    selected_value = $(selector).val()
    if selected_value.length > 0
      selected_value = wsrc.utils.to_int(selected_value)
    else
      selected_value = null
    return selected_value

  # find an existing match with the given player/team ids. The 
  @find_match_for_ids: (valid_match_set, id1, id2) ->
    for match in valid_match_set
      if id1 == match.team1 and id2 == match.team2
        return [match, false]
      else if id1 == match.team2 and id2 == match.team1
        return [match, true]
    return [null, null]

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

  @on_submit: (form) ->
    form_controller = WSRC_result_form.get_controler(form)
    form_controller.handle_submit()
    
  load_scores_for_match: (existing_match, isreversed) ->
    team1_id = WSRC_result_form.get_selected_id @form.find("select[name='team1']")
    team2_id = WSRC_result_form.get_selected_id @form.find("select[name='team2']")
    
    unless existing_match
      [existing_match, isreversed] = WSRC_result_form.find_match_for_ids(@valid_match_set, team1_id, team2_id)

    if existing_match
      radios = @form.find("input[name='result_type']")
      if existing_match.walkover
        @set_result_type('walkover')
        winner_select = @form.find("select[name='walkover_result']")
        if existing_match.walkover == 1
          winner_select.val(existing_match.team1)
        else
          winner_select.val(existing_match.team2)
        winner_select.selectmenu("refresh")
        @handle_walkover_result_changed(winner_select[0])
      else
        @set_result_type('normal')
        p1idx = 0
        p2idx = 1
        idx = 1
        if isreversed
          p1idx = 1
          p2idx = 0
        for s in existing_match.scores
          @form.find(":input[name='team1_score#{ idx }']").val(s[p1idx])
          @form.find(":input[name='team2_score#{ idx }']").val(s[p2idx])
          idx += 1
        while idx <=5
          @form.find(":input[name='team1_score#{ idx }']").val("")
          @form.find(":input[name='team2_score#{ idx }']").val("")
          idx += 1
        @handle_score_changed()
    else
      @set_result_type('normal')
      for idx in [1..5]
        @form.find(":input[name='team1_score#{ idx }']").val("")
        @form.find(":input[name='team2_score#{ idx }']").val("")

  handle_submit: () ->
    selectors = (@form.find("select[name='team#{ p }']") for p in [1, 2])
    team_ids = (WSRC_result_form.get_selected_id(selector) for selector in selectors)
    [match, reversed] = WSRC_result_form.find_match_for_ids(@valid_match_set, team_ids[0], team_ids[1])
    csrf_token = @form.find("input[name='csrfmiddlewaretoken']").val()
    match.competition = @competition_data.id
    result_type = @form.find("input[name='result_type']:checked").val()
    if result_type == "walkover"
      winner_id = wsrc.utils.to_int(@form.find("select[name='walkover_result']").val())
      if winner_id == team_ids[0]
        match.walkover = if reversed then 2 else 1
      else
        match.walkover = if reversed then 1 else 2
    else
      for i in [1..5]
        for j in [1..2]
          score = @form.find(":input[name='team#{ j }_score#{ i }']").val()
          score = if wsrc.utils.is_valid_int(score) then wsrc.utils.to_int(score) else null
          team = j
          if reversed
            team = if j == 2 then 1 else 2
          match["team#{ team }_score#{ i }"] = score
          
    if match.id
      # update existing match result:
      url = "/data/match/#{ match.id }"
      wsrc.ajax.PUT(url, match,
        successCB: (data) =>
          if @submitted_callback
            @submitted_callback()
          return true
        failureCB: (xhr, status) => 
          alert("ERROR #{ xhr.status }: Failed to update match #{ url }\n\nReason: #{ xhr.responseText }\n\n")
          return false
        csrf_token: csrf_token
      )
    else
      # new match result:
      url = "/data/match/"
      wsrc.ajax.POST(url, match,
        successCB: (data) =>
          if @submitted_callback
            @submitted_callback()
          return true
        failureCB: (xhr, status) => 
          alert("ERROR #{ xhr.status }: Failed to create match #{ url }\n\nReason: #{ xhr.responseText }\n\n")
          return false
        csrf_token: csrf_token
      )

    return false

wsrc.utils.add_to_namespace("result_form", WSRC_result_form)
