
unless window.assert?
  window.assert = (condition, message) ->
    unless condition 
      throw message || "Assertion failed"
      
window.WSRC =

  set_on_and_off: (onid, offid) ->
    jQuery("##{ onid }").show()
    jQuery("##{ offid }").hide()

  competitiongroup_data: null

  list_lookup: (list, id, id_key) ->
    unless id_key?
      id_key = "id"
    for l in list
      if l[id_key] == id
        return l
    return null

  get_competition_for_id: (box_id) ->
    box_id = parseInt(box_id)
    this.list_lookup(this.competitiongroup_data.competitions_expanded, box_id)

  get_player_config: (box_id, player_id) ->
    players = this.get_competition_for_id(box_id).players
    player_id = parseInt(player_id)
    return this.list_lookup(players, player_id)

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
    
  ##
  # Helper function to show a modal click-through dialog
  ##
  show_error_dialog: (msg) ->
    # close any open popups
    allpopups = jQuery("div[data-role=popup]")
    idx = 0
    openpopups = []
    while (idx < allpopups.length)
      apopup = allpopups.eq(idx)
      if apopup.parent().hasClass("ui-popup-active")
        openpopups.push(apopup)
        apopup.popup("close")
      idx += 1
    popupdiv = jQuery("#errorPopupDialog")
    popupdiv.find("div[role='main'] h3").html(msg)
    popupdiv.popup(
      afterclose: (event, ui) =>
        for apopup in openpopups
          apopup.popup("open")
    )
    popupdiv.popup("open")
    return true

  ##
  # Helper function for Ajax requests back to the server.
  # URL is the request url, should not include query params
  # DATA is an object which will be sent back as JSON
  # OPTS is an object containing:
  #  successCB - function to call back when successful
  #  failureCB - function to call back when there is an error
  #  csrf_token - (optional) CSRF token to be passed back to server
  # METHOD is the http CRUD type
  ## 
  ajax_helper: (url, data, opts, method) ->
    jQuery.mobile.loading("show", 
      text: ""
      textVisible: false
      textonly: false
      theme: "a"
      html: ""
    )
    headers = {}
    if opts.csrf_token?
      headers["X-CSRFToken"] = opts.csrf_token
    jQuery.ajax(
      url: url
      type: method
      data: data
      dataType: "json"
      headers: headers
      success: opts.successCB
      error: opts.failureCB
      complete: (xhr, status) ->
        jQuery.mobile.loading("hide") 
    )
    return null

  ajax_GET: (url, opts) ->
    this.ajax_helper(url, null, opts, "GET")

  ajax_POST: (url, data, opts) ->
    this.ajax_helper(url, data, opts, "POST")
    
  ajax_PUT: (url, data, opts) ->
    this.ajax_helper(url, data, opts, "PUT")


  ##
  # Configure and show the box detail popup for the league from which it was opened
  ##
  open_box_detail_popup: (anchor_id) ->
    box_id = anchor_id.replace("link-", "")
    jQuery("input#competition_id").val(box_id)
    this_box_config = this.get_competition_for_id(box_id)

    # setup page and inputs
    dialogdiv = jQuery("div#boxDetailDialog")
    dialogdiv.find("div h2").text(this_box_config.name) # page title

    setupPointsTable = () =>
      tablebody = dialogdiv.find("table#league-table tbody")

      # remove existing rows
      tablebody.find("tr").remove()
  
      newTotals = () -> {p: 0, w: 0, d: 0, l: 0, f: 0, a: 0, pts: 0}
      
      # sum up the totals for each result
      player_totals = {}
      if this_box_config?
        for r in this_box_config.matches
          for i in [1..2]
            player_id = r["player#{ i }"]
            totals = player_totals[player_id]
            unless totals?
              totals =  player_totals[player_id] = newTotals()
            totals.p += 1
            mine = i-1
            theirs = (if i == 1 then 1 else 0)
            for s in r.scores
              totals.f += s[mine]
              totals.a += s[theirs]
            if r.points[mine] > r.points[theirs]
              totals.w += 1
            else if r.points[mine] < r.points[theirs]
              totals.l += 1
            else
              totals.d += 1
            totals.pts += r.points[mine]

      # add in zeros for players without results, and enrich with player name
      for player in this_box_config.players
        if player.id of player_totals
          player_totals[player.id].name = player.full_name
        else
          totals = newTotals()
          totals.name = player.full_name
          player_totals[player.id] = totals

      # vectorize and sort
      player_totals = (totals for id,totals of player_totals)
      player_totals.sort((l,r) ->
        result = r.pts - l.pts
        if result == 0
          result = (r.f-r.a) - (l.f-l.a)
          if result == 0
            result = r.full_name < l.full_name
        result
      )

      # finally add rows to the table
      for totals in player_totals
        tablebody.append("<tr><th>#{ totals.name }</th><td>#{ totals.p }</td><td>#{ totals.w }</td><td>#{ totals.d }</td><td>#{ totals.l }</td><td>#{ totals.f }</td><td>#{ totals.a }</td><td class='score_total'>#{ totals.pts }</td></tr>")
#      tablebody.closest("table#league-table").table().table("refresh").trigger("create")

    setupResults = () =>
      resultsdiv = dialogdiv.find("div#league-results-div>div") # first child of the wrapper div

      # remove existing results
      resultsdiv.find("div").remove()
      resultsdiv.find("p").remove()

      if this_box_config?.matches?
        results = this_box_config.matches
        results.sort((l,r) ->
          l.timestamp > r.timestamp
        )
        id2NameMap = {} 
        for p in this_box_config.players
          id2NameMap[p.id] = p.full_name
        for r in results
          date = "Sat 4th June 2014" # TODO - convert from results
          gameswon = for i in [0..1]
            won = 0
            for s in r.scores
              if s[i] > s[1-i] then won += 1
            won
          first = if (r.points[0] > r.points[1]) then 0 else 1
          second = 1 - first
          opponents = [id2NameMap[r.player1], id2NameMap[r.player2]]
          scores = ("(<span #{ if s[first] > s[second]  then 'class=\"winner\"' else '' }>#{ s[first] }</span>, <span #{ if s[second] > s[first]  then 'class=\"winner\"' else '' }>#{ s[second] }</span>)" for s in r.scores).join(" ")
          html = "<div class='date'>#{ date }</div><div class='result'>#{ opponents[first] } <span #{ if r.points[first] > r.points[second]  then 'class=\"winner\"' else '' }>#{ gameswon[first] }</span>-#{ gameswon[second] } #{ opponents[second] }</div><div class='scores'>#{ scores }</div><p></p>"
          resultsdiv.append(html)
        resultsdiv.trigger("create") # ask JQM to do style the new box
      return null
      
    setupAddScoreDialog = () =>
      # get form and disable most inputs
      form = dialogdiv.find("form#add-change-form")    
      form.find("table td input").textinput().textinput("disable")
      form.find("input#result_type_normal").prop("checked",true).checkboxradio().checkboxradio("refresh");
      form.find("input#result_type_walkover").prop("checked",false).checkboxradio().checkboxradio("refresh");
      this.set_on_and_off('score-entry-input', 'walkover_input')
      form.find("input[type='radio']").checkboxradio().checkboxradio('disable')
      form.find("button[type='button']").prop('disabled', true)
      form.find("table#score-entry-input th#header-player1").text("Player 1")
      form.find("table#score-entry-input th#header-player2").text("Player 2")
  
      # add players from originating box to the player drop-downs 
      players = (p for p in this_box_config.players)
      players.sort((lhs,rhs) -> lhs.full_name > rhs.full_name)
      list = ([p.id, p.full_name] for p in players)
      list.unshift(["", "Player 1"])
      this.fill_select(form.find("select#player1"), list, null, true)
      list[0][1] = "Player 2"
      this.fill_select(form.find("select#player2"), list, null, true)
      return null

    setupPointsTable()
    setupResults()
    setupAddScoreDialog()
    dialogdiv.find("div#add-change-div").collapsible().collapsible("expand")
    return null

  load_scores_for_match: (cfg, players) ->
    existing_match = null
    p1idx = 0
    p2idx = 1
    if players?
      for match in cfg.matches
        if players[0] == match.player1 and players[1] == match.player2
          existing_match = match
          break
        else if players[0] == match.player2 and players[1] == match.player1
          existing_match = match
          p1idx = 1
          p2idx = 0
          break
    form = jQuery("div#boxDetailDialog form#add-change-form")
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
    form = jQuery("div#boxDetailDialog form#add-change-form")
    box_id = parseInt(form.find("input#competition_id").val())
    this_box_config = this.get_competition_for_id(box_id)

    players = (p for p in this_box_config.players)
    players.sort((lhs,rhs) -> lhs.full_name > rhs.full_name)
        
    selector = form.find("select##{ selector_id }")
    selected_player_id = parseInt(selector.val())
    opponents = []
    selected_player = this.list_lookup(players, selected_player_id)
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
      other_player = this.list_lookup(players, other_player_id)
      if other_player?
        opponents.push(other_player)
        opponents.reverse() if selector_id == "player2"

    checkBothPlayersSelected = () =>
      if opponents.length == 2
        # we have names for both players; enable the other inputs:
        form.find("input[type='radio']").checkboxradio('enable')
        form.find("table td input").textinput("enable")
        # load existing points record, if any:
        opponent_ids = (p.id for p in opponents)
        this.load_scores_for_match(this_box_config, opponent_ids)
        # and add players to the walkover result combo:
        this.fill_select(form.find("select#walkover_result"), ([p.id, p.full_name] for p in opponents))
      else
        # blank the scores:
        this.load_scores_for_match(this_box_config, null)

    checkBothPlayersSelected()
    this.validate_match_result()
    return null

  validate_match_result: () ->
    form = jQuery("div#boxDetailDialog form#add-change-form")
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
    form = jQuery("div#boxDetailDialog form#add-change-form")
    scores = 
      for i in [1..5]
        [
          form.find("input#team1_score#{ i }").val()
          form.find("input#team2_score#{ i }").val()
        ]
    selects = (form.find("select##{ p }") for p in ['player1', 'player2'])
    player_ids = (parseInt(e.val()) for e in selects)
    match_id_field = form.find("input#match_id")
    csrf_token = form.find("input[name='csrfmiddlewaretoken']").val()
    data = {
      player1: player_ids[0],
      player2: player_ids[1]
      box_id: box_id,
      scores: scores,
    }
    match_id = match_id_field.val()
    if match_id?
      # update existing match result:
      data.id = match_id
      url = "/comp_data/match/#{ match_id }"
      this.ajax_PUT(url, data,
        successCB: (data) =>
          return true
        failureCB: (xhr, status) => 
          this.show_error_dialog("ERROR: Failed to load data from #{ url }")
          return false
        csrf_token: csrf_token
      )
    else
      # new match result:
      url = "/comp_data/match/"
      this.ajax_POST(url, data,
        successCB: (data) =>
          return true
        failureCB: (xhr, status) => 
          this.show_error_dialog("ERROR: Failed to load data from #{ url }")
          return false
        csrf_token: csrf_token
      )

    return false
    

  refresh_all_box_data: (competitiongroup_data) ->
    this.competitiongroup_data = competitiongroup_data

    getTableCell = (table, player1Id, player2Id, playerIdToIndexMap) ->
      p2idx = playerIdToIndexMap[player2Id]
      offset = parseInt(p2idx) + 3
      table.find("tr#player-#{ player1Id } :nth-child(#{ offset })")

    for this_box_config in competitiongroup_data.competitions_expanded
      idx = 0
      playerIdToIndexMap = {}
      players = this_box_config.players
      while idx < players.length
        playerIdToIndexMap[players[idx].id] = idx
        idx += 1
      
      jbox = jQuery("table#table-#{ this_box_config.id }")
      totals = {}
      addScore = (player, score) ->
        unless player of totals
          totals[player] = 0
        totals[player] += score
      for result in this_box_config.matches
        getTableCell(jbox, result.player1, result.player2, playerIdToIndexMap).text(result.points[0])
        getTableCell(jbox, result.player2, result.player1, playerIdToIndexMap).text(result.points[1])
        addScore(result.player1, result.points[0])
        addScore(result.player2, result.points[1])
      jbox.find("tbody tr").each((idx,elt) ->
        if elt.id?
          elt.lastElementChild.textContent = totals[elt.id.replace("player-", "")] ? "0"
      )
    return true

  setup_events: () ->
    form = jQuery("div#boxDetailDialog form#add-change-form")
    form.find("input[name^='player']").on("change", () =>
      this.validate_match_result()
    )
    form.find("input[name^='team']").on("change", () =>
      this.validate_match_result()
    )
    form.find("input#result_type_normal").on("change", () =>
      this.set_on_and_off('score-entry-input', 'walkover_input')
      this.validate_match_result()
    )
    form.find("input#result_type_walkover").on("change", () =>
      this.set_on_and_off('walkover_input', 'score-entry-input')
      this.validate_match_result()
    )
    form.find("select#walkover_result").on("change", () =>
      this.validate_match_result()
    )

  onBoxActionClicked: (link) ->
    this.open_box_detail_popup(link.id)

  onPlayerSelected: (selector) ->
    this.on_player_selected(selector.id)

  onLeaguePageShow: (competitiongroup_id) ->
    this.setup_events()
    url = "/comp_data/competitiongroup/#{ competitiongroup_id }?expand=1"
    this.ajax_GET(url,
      successCB: (data) =>
        this.refresh_all_box_data(data)
        return true
      failureCB: (xhr, status) => 
        this.show_error_dialog("ERROR: Failed to load data from #{ url }")
        return false
    )


