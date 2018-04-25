
class WSRC_result_form

  # Handles interactions and maintains state for the result entry form. The form goes through a number of states:
  # 1. Opponents unselected (drop-downs contain all opponents)
  # 2. 1 opponent selected. other drop-down contains valid opponents for the first opponent selection
  # 3. Both opponents selected - score-entry and walkover permitted
  # 4a if walkover is non-null - disable score entry
  # 4b otherwise score-entry must have at least one score populated
  # 5. Ready for submit 

  constructor: (@form, @competition_data, @entrants_map, @match_id, @base_path, @base_path_suffix) ->
    @team1_selector = @form.find("select[name='team1']")
    @team2_selector = @form.find("select[name='team2']")
    @match_selector = @form.find(":input[name='match']")
    @team1_selector.on('change', (evt) => @handle_team_selected(evt))
    @team2_selector.on('change', (evt) => @handle_team_selected(evt))
    @match_selector.on("change", (evt) => @handle_match_changed(evt))
    @form.find(":input[name='walkover']").on("change", (evt) => @handle_result_type_changed(evt))
    @form.find("table.score-entry :input").on("change", (evt) => @handle_score_changed(evt))
    unless @match_id?
      if @team1_selector.length
        @handle_team_selected({target: @team1_selector});
      if @team2_selector.length
        @handle_team_selected({target: @team2_selector});
    @do_validation()

  toggle_disabled: (selector, enable) ->    
    jqelt = if selector.jquery? then selector else @form.find(selector)
    if enable
      jqelt.removeAttr("disabled")
      jqelt.prop("disabled", false)
      jqelt.removeProp("disabled")
    else
      jqelt.prop("disabled", true)
      jqelt.attr("disabled", "disabled")
    return null

  set_opponent_name: (name, op_1_or_2) ->
    unless name
      name = "Opponent #{ op_1_or_2 }"
    @form.find("table.score-entry th.header-team#{ op_1_or_2 }").text(name)
    radio = @form.find("label > :input[name='walkover'][value='#{ op_1_or_2 }']")
    radio.next(".label-text").text(name)
    
  
  handle_team_selected: (evt) ->
    selector = $(evt.target)
    team_id = WSRC_result_form.get_selected_id(selector)
    text = if team_id then @entrants_map[team_id].name else null
    name = selector.attr("name")
    op_1_or_2 = name.slice(-1)
    @set_opponent_name(text, op_1_or_2)
    invalid_opponents = true
    if team_id
      other_idx = if op_1_or_2 == "1" then "2" else "1"
      other_selector = @form.find("select[name='team#{ other_idx }']")
      other_team_id = WSRC_result_form.get_selected_id(other_selector)
      @toggle_disabled(other_selector, true)
      if team_id == other_team_id
        other_selector.val("")
        other_team_id = null
      other_selector.find("option").each (idx, elt) ->
        if parseInt(elt.value, 10) == team_id
          $(elt).hide()
        else
          $(elt).show()
      if other_team_id?
        if op_1_or_2 == "1"
          @load_scores_for_opponents(team_id, other_team_id)
        else
          @load_scores_for_opponents(other_team_id, team_id)
        invalid_opponents = false
    if invalid_opponents
      @blank_scores()
      @set_action()
    @do_validation()

  handle_result_type_changed: (evt) ->
    @do_validation()

  handle_score_changed: () ->
    @do_validation()
    
  handle_match_changed: (evt) ->
    selector = $(evt.target)
    @match_id = selector.val() or null
    if @match_id
      @match_id = parseInt(@match_id, 10)
      match = (amatch for amatch in @competition_data.matches when amatch.id == @match_id)
      match = if match.length then match[0] else null
      @set_opponent_name(@entrants_map[match?.team1]?.name, 1)
      @set_opponent_name(@entrants_map[match?.team2]?.name, 2)
      @load_scores_for_match(match)
      @do_validation()
    
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
        row_total = Math.abs(parseInt(val1, 10)) + Math.abs(parseInt(val2, 10))
        if isNaN(row_total) or row_total == 0
          return false
        total += row_total
      else
        blank_row_found = true
    return not isNaN(total) and total > 0

  validate_match: () ->
    if @match_selector.length == 0
      return true
    return @match_selector.val()

  validate_players: () ->
    if @team1_selector.length == 0 and @team2_selector.length == 0
      return true # selectors have been removed
    val = WSRC_result_form.get_selected_id(@team1_selector) and WSRC_result_form.get_selected_id(@team2_selector)
    return val?

  validate_walkover: () ->
    walkover_result = @form.find("input[name='walkover']:checked").val()
    return walkover_result?.length > 0
    
  do_validation: () ->
    is_valid = false
    if @validate_players() and @validate_match()
      is_walkover = @validate_walkover()
      @toggle_disabled(":input[name='walkover']", true)
      @toggle_disabled("table.score-entry :input", not is_walkover)
      is_valid = is_walkover or @validate_scores()
      @toggle_disabled("button[type='submit']", is_valid)
#      if is_walkover
#        @blank_scores()
    else
      @toggle_disabled(":input[name='walkover']", false)
      @toggle_disabled("table.score-entry :input", false)
      @toggle_disabled("button[type='submit']", false)
    return is_valid

  @get_selected_id: (selector) ->
    selected_value = $(selector).val()
    if selected_value?.length > 0
      selected_value = parseInt(selected_value, 10)
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

  blank_scores: () ->
    @form.find("table.score-entry :input").val("")
    radio = @form.find("input[name='walkover'][value='']")
    radio.prop("checked", true)


  load_scores_for_opponents: (team1_id, team2_id) ->
    [existing_match, isreversed] = WSRC_result_form.find_match_for_ids(@competition_data.matches, team1_id, team2_id)
    @load_scores_for_match(existing_match, isreversed)
    action = ""
    if existing_match
      action = @base_path + "/#{ existing_match.id }"  + @base_path_suffix
    @set_action(action)

  set_action: (action) ->
    if action
      history_url = action
    else
      action = history_url = @base_path + @base_path_suffix
    if history
      history.pushState({}, "", history_url)
    @form[0].action = action

  load_scores_for_match: (existing_match, isreversed) ->
    @blank_scores()
    if existing_match
      if existing_match.walkover
        radio = @form.find("input[name='walkover'][value='#{ existing_match.walkover }']")
        radio.prop("checked", true)
      else
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
    
unless window.wsrc
  window.wsrc = {}
window.wsrc.result_form =  WSRC_result_form
