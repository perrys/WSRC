window.WSRC_result_form =

  ##
  # Remove non-empty items from the selector and replace with the given list
  ## 
  fill_select: (selector, list, selected_val, remove_empty) ->
    remove_empty = remove_empty? and true or false
    elt = selector[0] # get the DOM element
    for i in [(elt.options.length-1)..0] by -1
      if remove_empty or elt.options[i].value != ""
        elt.remove(i)
    for item in list
      opt = jQuery("<option value='#{ item[0] }'>#{ item[1] }</option>")
      selector.append(opt)
      if item[0] == selected_val
        opt.prop('selected': true)
    selector.selectmenu();
    selector.selectmenu('refresh', true);
    return null
    
  setup_result_form: () =>
    # get form and disable most inputs
    form = $("form#add-change-form")    
    form.find("table td input").textinput().textinput("disable")
    form.find("input#result_type_normal").prop("checked",true).checkboxradio().checkboxradio("refresh");
    form.find("input#result_type_walkover").prop("checked",false).checkboxradio().checkboxradio("refresh");
    WSRC_utils.set_on_and_off('score-entry-input', 'walkover_input')
    form.find("input[type='radio']").checkboxradio().checkboxradio('disable')
    form.find("button[type='button']").prop('disabled', true)
    form.find("table#score-entry-input th#header-player1").text("Player 1")
    form.find("table#score-entry-input th#header-player2").text("Player 2")

    # add players from originating box to the player drop-downs 
    players = (p.player for p in this_box_config.entrants)
    players.sort((lhs,rhs) -> lhs.full_name > rhs.full_name)
    list = ([p.id, p.full_name] for p in players)
    list.unshift(["", "Player 1"])
    selected_val = WSRC_user_player_id ? null
    this.fill_select(form.find("select#player1"), list, selected_val, true)
    list[0][1] = "Player 2"
    this.fill_select(form.find("select#player2"), list, null, true)
    if selected_val?
      for e in this_box_config.entrants
        if e.player.id == selected_val
          this.on_player_selected("player1")
          break
    return null

  result_type_changed: () ->
    form = jQuery("form#add-change-form")
    result_type = form.find("input[name='result_type']:checked").val()
    if result_type == "normal"
      WSRC_utils.set_on_and_off('score-entry-input', 'walkover_input')
    else
      WSRC_utils.set_on_and_off('walkover_input', 'score-entry-input')
    return true

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

      
  ##
  # Setup the input form when one of the players is selected in the add score section
  ##
  on_player_selected: (selector_id) ->
    form = jQuery("form#add-change-form")
    box_id = parseInt(form.find("input#competition_id").val())
    this_box_config = this.get_competition_for_id(box_id)

    players = (p.player for p in this_box_config.entrants)
    players.sort((lhs,rhs) -> lhs.full_name > rhs.full_name)
        
    selector = form.find("select##{ selector_id }")
    selected_player_id = parseInt(selector.val())
    opponents = []
    selected_player = WSRC_utils.list_lookup(players, selected_player_id)
    header = form.find("table#score-entry-input th#header-#{ selector_id }") 
    if selected_player?
      opponents.push(selected_player)
      header.text(selected_player.full_name)
    else
      header.text(selected_player.full_name)      

    valid_opponent_list = ([p.id, p.full_name] for p in players when (p.id != selected_player_id))
    
    other_selector_id = (selector_id == "player2") and "player1" or "player2"
    other_selector = form.find("select##{ other_selector_id }")
    other_player_id = other_selector.val()
    if other_player_id == ""
      this.fill_select(other_selector, valid_opponent_list)
    else
      other_player_id = parseInt(other_player_id)
      this.fill_select(other_selector, valid_opponent_list, other_player_id, true)
      other_player = WSRC_utils.list_lookup(players, other_player_id)
      if other_player?
        opponents.push(other_player)
        opponents.reverse() if selector_id == "player2"

    checkBothPlayersSelected = () =>
      if opponents.length == 2
        # we have names for both players; enable the other inputs:
        form.find("input[type='radio']").checkboxradio('enable')
        form.find("table td input").textinput("enable")
        # add players to the walkover result combo:
        this.fill_select(form.find("select#walkover_result"), ([p.id, p.full_name] for p in opponents))
        # load existing points record/walkover result, if any:
        opponent_ids = (p.id for p in opponents)
        this.load_scores_for_match(this_box_config, opponent_ids)
      else
        # blank the scores:
        this.load_scores_for_match(this_box_config, null)

    checkBothPlayersSelected()
    this.validate_match_result()
    return null

  validate_match_result: () ->
    form = jQuery("form#add-change-form")
    box_id = parseInt(form.find("input#competition_id").val())
    this_box_config = this.get_competition_for_id(box_id)
    result_type = form.find("input[name='result_type']:checked").val()
    valid = false

    if result_type == "normal"
      valid =
        parseInt(form.find("select#player1").val()) > 0 and
        parseInt(form.find("select#player2").val()) > 0 and
        (parseInt(form.find("input#team1_score1").val()) + parseInt(form.find("input#team2_score1").val())) > 0
    else if result_type == "walkover"
      valid = parseInt(form.find("select#walkover_result").val()) > 0

    submit_button = form.find("button#submit_match")
    submit_button.prop("disabled", not valid)
      

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
        if WSRC_utils.is_valid_int(score)
          data["team#{ j }_score#{ i }"] = parseInt(score)
    match_id = match_id_field.val()
    result_type = form.find("input[name='result_type']:checked").val()
    if result_type == "walkover"
      winner_id = parseInt(form.find("select#walkover_result").val())
      if winner_id == player_ids[0]
        data.walkover = 1
      else
        data.walkover = 2
    if WSRC_utils.is_valid_int(match_id) 
      # update existing match result:
      data.id = parseInt(match_id)
      url = "/data/match/#{ match_id }"
      WSRC_ajax.PUT(url, data,
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
      WSRC_ajax.POST(url, data,
        successCB: (data) =>
          return true
        failureCB: (xhr, status) => 
          this.show_error_dialog("ERROR: Failed to load data from #{ url }")
          return false
        csrf_token: csrf_token
      )

    return false
    
  setup_add_change_events: () ->
    form = jQuery("form#add-change-form")
    form.find("input[name^='player']").on("change", () =>
      this.validate_match_result()
      return true
    )
    form.find("input[name^='team']").on("change", () =>
      this.validate_match_result()
      return true
    )
    form.find("input#result_type_normal").on("change", () =>
      this.result_type_changed()
      this.validate_match_result()
      return true
    )
    form.find("input#result_type_walkover").on("change", () =>
      this.result_type_changed()
      this.validate_match_result()
      return true
    )
    form.find("select#walkover_result").on("change", () =>
      this.validate_match_result()
      return true
    )

