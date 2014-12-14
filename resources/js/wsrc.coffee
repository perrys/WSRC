
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

  is_valid_int: (i) ->
    if i == ""
      return false
    i = parseInt(i)
    return not isNaN(i)

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
    popupdiv.find("div.ui-content h3").html(msg)
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
          opponents = [id2NameMap[r.team1_player1], id2NameMap[r.team2_player1]]
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
      selected_val = WSRC_user_player_id ? null
      this.fill_select(form.find("select#player1"), list, selected_val, true)
      list[0][1] = "Player 2"
      this.fill_select(form.find("select#player2"), list, null, true)
      if selected_val?
        this.on_player_selected("player1")
      return null

    setupResults()
    setupAddScoreDialog()
    dialogdiv.find("div#add-change-div").collapsible().collapsible("expand")
    return null

  result_type_changed: () ->
    form = jQuery("form#add-change-form")
    result_type = form.find("input[name='result_type']:checked").val()
    if result_type == "normal"
      this.set_on_and_off('score-entry-input', 'walkover_input')
    else
      this.set_on_and_off('walkover_input', 'score-entry-input')
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
        if this.is_valid_int(score)
          data["team#{ j }_score#{ i }"] = parseInt(score)
    match_id = match_id_field.val()
    result_type = form.find("input[name='result_type']:checked").val()
    if result_type == "walkover"
      winner_id = parseInt(form.find("select#walkover_result").val())
      if winner_id == player_ids[0]
        data.walkover = 1
      else
        data.walkover = 2
    if this.is_valid_int(match_id) 
      # update existing match result:
      data.id = parseInt(match_id)
      url = "/data/match/#{ match_id }"
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
      url = "/data/match/"
      this.ajax_POST(url, data,
        successCB: (data) =>
          return true
        failureCB: (xhr, status) => 
          this.show_error_dialog("ERROR: Failed to load data from #{ url }")
          return false
        csrf_token: csrf_token
      )

    return false
    
  setup_points_table: (this_box_config) ->
    tablebody = jQuery("table#leaguetable-#{ this_box_config.id } tbody")


    tablerows = tablebody.find("tr")

    newTotals = () -> {p: 0, w: 0, d: 0, l: 0, f: 0, a: 0, pts: 0}
    
    # sum up the totals for each result
    player_totals = {}
    if this_box_config?
      for r in this_box_config.matches
        for i in [1..2]
          player_id = r["team#{ i }_player1"]
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
        totals.id = player.id

    # vectorize and sort
    for id,totals of player_totals
      totals.id = parseInt(id)
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
    idx = 0
    for totals in player_totals
      # do this with raw DOM as the jQuery was a little slow
      row = tablerows[idx]
      cell = row.firstChild
      for prop in ["name", "p", "w", "d", "l", "f" , "a", "pts"]
        while cell.nodeType != document.ELEMENT_NODE
          cell=cell.nextSibling
        cell.innerHTML = totals[prop]
        if totals.id == (WSRC_user_player_id ? -1)
          cell.className = "points wsrc-currentuser"
        else
          cell.className = "points"
        cell=cell.nextSibling
      ++idx

  refresh_all_box_data: (competitiongroup_data) ->
    this.competitiongroup_data = competitiongroup_data

    getTableCell = (table, player1Id, player2Id, playerIdToIndexMap) ->
      p2idx = playerIdToIndexMap[player2Id]
      offset = parseInt(p2idx) + 2
      row = table.find("#player-#{ player1Id }")
      # drop to DOM for speed:
      cell = row[0].firstChild
      idx = 0
      while true
        while cell.nodeType != document.ELEMENT_NODE
          cell=cell.nextSibling
        if idx == offset
          return cell
        cell=cell.nextSibling
        ++idx
      return row.find("td").eq(offset)

    setup_box = (this_box_config) ->
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
        getTableCell(jbox, result.team1_player1, result.team2_player1, playerIdToIndexMap).innerHTML = result.points[0]
        getTableCell(jbox, result.team2_player1, result.team1_player1, playerIdToIndexMap).innerHTML = result.points[1]
        addScore(result.team1_player1, result.points[0])
        addScore(result.team2_player1, result.points[1])
      jbox.find("tbody tr").each((idx,elt) ->
        if elt.id?
          $(elt).find("td").last().html(totals[elt.id.replace("player-", "")] ? "0")
      )
      
    for this_box_config in competitiongroup_data.competitions_expanded
      setup_box(this_box_config)
      this.setup_points_table(this_box_config)
      
    return true

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

  refresh_facebook: (data) ->
    table = $("#facebook_news tbody").show()
    table.parents(".jqm-block-content").find("p").hide()
    if data? and data.entries.length > 0
      table.find("tr").remove()
      odd = true
      for e in data.entries[0..7]
        dt = e.published
        dt = dt.substring(8,10) + "/" + dt.substring(5,7)
        row = $("<tr><td>#{ dt }</td><td>#{ e.title }</td><td><a href='" + e.alternate + "'>read</a></td></tr>")
        if odd
          row.addClass("odd")
          odd = false
        else
          row.addClass("even")
          odd = true
        table.append(row)


  refresh_tournament_data: (competition_data) ->

    players = {}
    for p in competition_data.players
      players[p.id] = p
    seedings = {}
    for s in competition_data.seedings
      seedings[s.player] = s.seeding
    
    populateMatch = (match) ->
  
      # start with the html cells for the player names
      baseSelector = "td#match_#{ competition_data.id  }_#{ match.competition_match_id }"
      team1Elt = jQuery(baseSelector + "_t")  # top cell
      team2Elt = jQuery(baseSelector + "_b")  # bottom cell
      for elt in [team1Elt, team2Elt]
        elt.removeClass("empty-match")
        elt.nextUntil(".seed", ".score").removeClass("empty-match")
        elt.prev(".seed").removeClass("empty-match")
  
      makeTeamName = (id1, id2) =>
        selector = (user) ->
          if id2
            return user.short_name 
          return user.full_name
        unless id1?
          return " "
        result = selector(players[id1])
        if id2
          result += " & " + selector(players[id2]) 
        return result.replace(" ", "&nbsp;")
        
      team1Name = makeTeamName(match.team1_player1, match.team1_player2) 
      team2Name = makeTeamName(match.team2_player1, match.team2_player2) 
      team1Elt.html(team1Name)
      team2Elt.html(team2Name)
  
      # now the seeds:
      addSeed = (id, elt) =>
        if id?
          seed = seedings[id]
          if seed?
            elt.prev().html(seed)
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
    # TODO: add events for highlighting and score dialog
    
    return true
      
  onBoxActionClicked: (link) ->
    this.open_box_detail_popup(link.id)

  onPlayerSelected: (selector) ->
    this.on_player_selected(selector.id)

  onTournamentSelected: (selector) ->
    link = "/tournament/" + $(selector).val()
    document.location = link

  onLeagueSelected: (selector) ->
    link = "/boxes/" + $(selector).val()
    document.location = link

  onTournamentPageShow: (page) ->
    competition_id = page.data().competitionid
    this.setup_add_change_events()

    url = "/data/competition/#{ competition_id }?expand=1"
    loadPageData = () =>
      this.ajax_GET(url,
        successCB: (data) =>
          this.refresh_tournament_data(data)
          return true
        failureCB: (xhr, status) => 
          this.show_error_dialog("ERROR: Failed to load tournament data from #{ url }")
          return false
      )
    loadPageData()

  onLeaguePageShow: (page) ->
    competitiongroup_id = page.data().competitiongroupid
    this.setup_add_change_events()
      
    url = "/data/competitiongroup/#{ competitiongroup_id }?expand=1"
    loadPageData = () =>
      this.ajax_GET(url,
        successCB: (data) =>
          this.refresh_all_box_data(data)
          return true
        failureCB: (xhr, status) => 
          this.show_error_dialog("ERROR: Failed to load data from #{ url }")
          return false
      )
    $("#box-refresh-button").click (evt) ->
      loadPageData()
    loadPageData()

    view_radios = $("#page-control-form input[name='view_type']")
    view_radios.on("change", (evt) ->
      view_type = view_radios.filter(":checked").val()
      if view_type == "tables"
        $("table.boxtable").hide()
        $("table.leaguetable").show()
      else
        $("table.leaguetable").hide()
        $("table.boxtable").show()
    )
    
  onHomePageShow: (page) ->
    last = $("#leaguemaster_last_result_idx").val()
    if last != ""
      idx = parseInt(last) - 5
      last = $("#leaguemaster_#{ idx }")
      if last.length == 1 and last[0].scrollIntoView?
        last[0].scrollIntoView();

    url = "/data/facebook"
    this.ajax_GET(url,
      successCB: (data) =>
        this.refresh_facebook(data)
        return true
      failureCB: (xhr, status) =>
        table = $("#facebook_news tbody").hide()
        err_container = table.parents(".jqm-block-content").find("p").show()
        err_container.html(xhr.responseText)    
        return false
    )
    $('.bxslider').bxSlider(
      mode: 'horizontal',
      slideWidth: 460,
      captions: false,
      randomStart: true,
      controls: false,
      auto: true,
      pause: 7000,
    );


  onPageContainerShow: (evt, ui) ->
    newpage = ui.toPage
    pagetype = newpage.data().pagetype
    if pagetype == "home"
      this.onHomePageShow(newpage)
    else if pagetype == "boxes"
      this.onLeaguePageShow(newpage)
    else if pagetype == "tournament"
      this.onTournamentPageShow(newpage)

    $("#box_link").click(() ->
      document.location.pathname="/competitions/leagues"
    )

    location.search.substr(1).split("&").forEach( (pair) ->
      if (pair == "")
        return
      parts = pair.split("=")
      if parts[0] == "scrollto"
        callback = () -> $.mobile.silentScroll($("#" + parts[1])[0].offsetTop)
        window.setTimeout(callback, 500)
    )

  
