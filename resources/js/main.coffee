
unless window.assert?
  window.assert = (condition, message) ->
    unless condition 
      throw message || "Assertion failed"
      
window.WSRC =

  toggle: (onid, offid) ->
    # TODO - remove - jQuery provides this already
    jQuery("##{ onid }").css("display", "")
    jQuery("##{ offid }").css("display", "none")

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

  ##
  # Remove non-empty items from the selector and replace with the given list
  ## 
  fill_select: (selector, list) ->
    elt = selector[0] # get the DOM element
    for i in [(elt.options.length-1)..0] by -1
      if elt.options[i].value != ""
        elt.remove(i)
    for item in list
      selector.append("<option value='#{ item.id }'>#{ item.full_name }</option>")
    selector.selectmenu();
    selector.selectmenu('refresh', true);
    return null
    
  ##
  # Helper function to show a modal click-through dialog
  ##
  show_error_dialog: (msg) ->
    popupdiv = jQuery("#errorPopupDialog")
    popupdiv.find("div[role='main'] h3").html(msg)
    popupdiv.popup()
    popupdiv.popup("open")
    return true

  ##
  # Helper function for Ajax requests back to the server.
  # URL is the request url, including query params if any
  # OPTS is an object containing:
  #  successCB - function to call back when successful
  #  failureCB - function to call back when there is an error
  ## 
  ajax_GET: (url, opts) ->
    jQuery.mobile.loading( "show", 
      text: ""
      textVisible: false
      textonly: false
      theme: "a"
      html: ""
    )
    jQuery.ajax(
      url: url
      type: "GET"
      dataType: "json"
      success: opts.successCB
      error: opts.failureCB
      complete: (xhr, status) ->
        jQuery.mobile.loading( "hide" ) 
    )
    return true

  ##
  # Helper function for Ajax requests back to the server.
  # URL is the request url, should not include query params
  # DATA is an object which will be sent back as JSON
  # OPTS is an object containing:
  #  successCB - function to call back when successful
  #  failureCB - function to call back when there is an error
  ## 
  ajax_POST: (url, data, opts) ->
    jQuery.mobile.loading("show", 
      text: ""
      textVisible: false
      textonly: false
      theme: "a"
      html: ""
    )
    jQuery.ajax(
      url: url
      type: "POST"
      data: data
      dataType: "json"
      success: opts.successCB
      error: opts.failureCB
      complete: (xhr, status) ->
        jQuery.mobile.loading("hide") 
    )


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
      this.toggle('score-entry-input', 'walkover_input')
      form.find("input[type='radio']").checkboxradio().checkboxradio('disable')
      form.find("button[type='button']").prop('disabled', true)
      form.find("table#score-entry-input th#header-player1").text("Player 1")
      form.find("table#score-entry-input th#header-player2").text("Player 2")
  
      # add players from originating box to the player drop-downs 
      players = (p for p in this_box_config.players)
      players.sort((lhs,rhs) -> lhs.full_name - rhs.full_name)
      this.fill_select(form.find("select#player1"), players)
      this.fill_select(form.find("select#player2"), players)

    setupPointsTable()
    setupResults()
    setupAddScoreDialog()
    dialogdiv.find("div#add-change-div").collapsible().collapsible("expand")
    return null

  load_scores_for_match: (cfg, players) ->
    scores = null
    p1idx = 0
    p2idx = 1
    if players?
      for match in cfg.matches
        if players[0] == match.player1 and players[1] == match.player2
          scores = match.scores
          break
        else if players[0] == match.player2 and players[1] == match.player1
          scores = match.scores
          p1idx = 1
          p2idx = 0
          break
    form = jQuery("div#boxDetailDialog form#add-change-form")
    idx = 1
    if scores?
      for s in scores
        form.find("input#team1_score#{ idx }").val(s[p1idx])
        form.find("input#team2_score#{ idx }").val(s[p2idx])
        idx += 1
    while idx <=5
      form.find("input#team1_score#{ idx }").val("")
      form.find("input#team2_score#{ idx }").val("")
      idx += 1
  
  ##
  # Setup the input form when one of the players is selected in the add score section
  ##
  on_player_selected: (selector_id) ->
    form = jQuery("div#boxDetailDialog form#add-change-form")
    selector = form.find("select##{ selector_id }")
    element = selector[0]
    selectedId = element.options[element.selectedIndex].value
    selectedName = element.options[element.selectedIndex].text

    # set the headers and manipulate avaiable players in the other selector if it is unselected:
    form.find("table#score-entry-input th#header-#{ selector_id }").text(selectedName)
    otherid = (selector_id == "player2") and "player1" or "player2"
    otherselector = form.find("select##{ otherid }")
    if otherselector.val() == ""
      players = ([p.value, p.textContent] for p in selector.find("option") when (p.value != "" and p.value != selectedId))
      this.fill_select(otherselector, ({id:p[0], full_name:p[1]} for p in players))
      # TODO - remove selected player from other selector even if it is not empty

    checkBothPlayersSelected = () =>
      selects = (form.find("select##{ p }") for p in ['player1', 'player2'])
      if (selects[0].val() == "" or selects[1].val() == "")
        # blank the scores:
        this.load_scores_for_match(this_box_config, null)
      else
        box_id = jQuery("input#competition_id").val()
        this_box_config = this.get_competition_for_id(box_id)
        # we have names for both players; enable the other inputs:
        form.find("input[type='radio']").checkboxradio('enable')
        form.find("table td input").textinput("enable")
        # load existing points record, if any:
        player_ids = (parseInt(e.val()) for e in selects)
        this.load_scores_for_match(this_box_config, player_ids)
        # and add players to the walkover result combo:
        dom_selects = (e[0] for e in selects)
        player_selects = {id:e.options[e.selectedIndex].value, full_name:e.options[e.selectedIndex].text} for e in dom_selects
        this.fill_select(form.find("select#walkover_result"), player_selects)

    checkBothPlayersSelected()
    return null

  submit_match_result: () ->
    box_id = parseInt(jQuery("input#competition_id").val())
    this_box_config = this.get_competition_for_id(box_id)
    form = jQuery("div#boxDetailDialog form#add-change-form")
    scores = 
      for i in [1..5]
        [
          form.find("input#team1_score#{ idx }").val()
          form.find("input#team2_score#{ idx }").val()
        ]
    selects = (form.find("select##{ p }") for p in ['player1', 'player2'])
    player_ids = (parseInt(e.val()) for e in selects)
    

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
      
  onBoxActionClicked: (link) ->
    this.open_box_detail_popup(link.id)

  onPlayerSelected: (selector) ->
    this.on_player_selected(selector.id)

  onLeaguePageShow: (competitiongroup_id) ->
    url = "/comp_data/competitiongroup/#{ competitiongroup_id }?expand=1"
    this.ajax_GET(url,
      successCB: (data) =>
        this.refresh_all_box_data(data)
        return true
      failureCB: (xhr, status) => 
        this.show_error_dialog("ERROR: Failed to load data from #{ url }")
        return false
    )


