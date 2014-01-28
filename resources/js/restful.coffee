
window.WSRC =

  BASE_URL: "/tournaments"
  PROXY_PREFIX: if document.URL == "http://localhost/" then "" else ".php"

#  HIGHLIGHT_CLASS: "ui-state-hover" # includes bg image which changes dimensions
  HIGHLIGHT_CLASS: "wsrc-highlight"
  MIN_WIDTH: 100
  COMP_PADDING: 10
  ignore_change_events: false
  competitions: {}


  errorDialog: (msg) ->
    jQuery("#dialog-confirm").html(msg)
    jQuery("#dialog-confirm").dialog(
      resizable: false
      height:200 
      width: 300
      modal: true
      title: "ERROR"
      buttons: 
        "Close": () ->
          jQuery( this ).dialog( "close" )
    )
    return true

    
  loadFromServer: (url, opts) ->
    if opts.loadMaskId?
      jQuery(opts.loadMaskId).mask("Loading...")
    jQuery.ajax(
      url: this.BASE_URL + url
      type: "GET"
      dataType: "json"
      success: opts.successCB
      error: opts.failureCB
      complete: (xhr, status) ->
        if opts.loadMaskId?
          jQuery(opts.loadMaskId).unmask()
    )
    return true

    
  bindEvents: (comp_id) ->
    HIGHLIGHT_CLASS = this.HIGHLIGHT_CLASS
    playerElts = jQuery("div#comp_#{ comp_id } td.player").filter(() -> this.innerHTML != "&nbsp;")
    playerElts.mouseenter (evt) -> 
      matches = jQuery("div#comp_#{ comp_id } td.player").filter(() -> this.innerHTML == evt.target.innerHTML)
      matches.addClass(HIGHLIGHT_CLASS)
    playerElts.mouseleave (evt) ->      
      jQuery("div#comp_#{ comp_id } td.#{ HIGHLIGHT_CLASS }").removeClass(HIGHLIGHT_CLASS)
    scoreDialog = (elt) =>
      tokens = elt.id.split("_")
      comp = tokens[1]
      matchId = parseInt(tokens[2])
      match = this.competitions[comp][matchId]
      this.showScoreEntryDialog([match])
      
    playerElts.dblclick (evt) ->
      scoreDialog(evt.target)
    playerElts.siblings().filter(".score").dblclick (evt) ->
      target = evt.target;
      while not target.classList.contains("player") # TODO - support older browsers
        target = target.previousSibling
      scoreDialog(target)
    return true

    
  populateByes: (comp_id, comp_nRounds) ->
    min_id = 1<<(comp_nRounds-1)
    findFirstColumnEmptyCells = (cell) ->
      if this.innerHTML != "&nbsp;"
        return false
      tokens = this.id.split("_")
      matchId = parseInt(tokens[2]) 
      return matchId >= min_id
    emptyElts = jQuery('div#comp_' + comp_id + ' td.player').filter(findFirstColumnEmptyCells)
    emptyElts.addClass("bye")      
    emptyElts.nextUntil(".seed", ".score").addClass("bye")      
    emptyElts.prev(".seed").addClass("bye")      
    emptyElts.nextUntil(".seed", ".bottomlink").removeClass("bottomlink")      
    return true

  findWinner: (scores) ->
    wins = [0,0]
    injury = false
    for [score1, score2] in scores 
      if score1 > score2
        ++wins[0]
      else if score1 < score2
        ++wins[1]
      injury = injury or score1 < 0 or score2 < 0 
    return {
      wins: wins
      injury: injury        
    }
    
  clearCompetition: (comp_id) ->
    jQuery("div#comp_" + comp_id + " td.seed").html("&nbsp;")
    jQuery("div#comp_" + comp_id + " td.player").html("&nbsp;")
    jQuery("div#comp_" + comp_id + " td.score").html("&nbsp;")
    

  populateMatch: (comp, match_id, match) ->
    baseSelector = "div#comp_" + comp.id + " td#match_" + comp.id + "_" + match_id
    team1Elt = jQuery(baseSelector + "_t") 
    team2Elt = jQuery(baseSelector + "_b") 

    userName = (id1, id2) =>
      selector = (user) ->
        if id2
          if user.shortname
            return user.shortname 
        return user.name
      unless id1?
        return " "
      result = selector(this.players[id1])
      if id2
        result += " & " + selector(this.players[id2]) 
      return result
      
    team1Name = userName(match.Team1_Player1_Id, match.Team1_Player2_Id) 
    team2Name = userName(match.Team2_Player1_Id, match.Team2_Player2_Id) 
    team1Elt.html(team1Name.replace(" ", "&nbsp;"))
    team2Elt.html(team2Name.replace(" ", "&nbsp;"))

    addSeed = (id, elt) =>
      if id?
        if (seed = this.players[id].seeding[comp.id])?
          elt.prev().html(seed)
    addSeed(match.Team1_Player1_Id, team1Elt)
    addSeed(match.Team2_Player1_Id, team2Elt)
        
    if match.Team1_Player1_Id? and match.Team2_Player1_Id
      team1ScoreElt = team1Elt.next()
      team2ScoreElt = team2Elt.next()
      scores = []
      for setNumber in [1..5]
        scores.push([match["Team1_Score#{ setNumber }"], match["Team2_Score#{ setNumber }"]])
      result = this.findWinner(scores)
      unless result.injury
        for [team1Score, team2Score] in scores
          if team1Score? and team2Score?
            team1ScoreElt.html(team1Score)
            team2ScoreElt.html(team2Score)
          else
            team1ScoreElt[0].innerHTML = "&nbsp;"
            team2ScoreElt[0].innerHTML = "&nbsp;"
          if team1Score > team2Score
            team1ScoreElt.addClass("winningscore")
          else if team1Score < team2Score
            team2ScoreElt.addClass("winningscore")
          team1ScoreElt = team1ScoreElt.next()
          team2ScoreElt = team2ScoreElt.next()
      if result.wins[0] > result.wins[1]
        team1Elt.addClass("winner")
      else if result.wins[0] < result.wins[1]
        team2Elt.addClass("winner")
      if match["Team1_Score1"] < 0
        team1Elt.css("text-decoration", "line-through")
      if match["Team2_Score1"] < 0
        team2Elt.css("text-decoration", "line-through")
        
    match.team1_name = team1Name
    match.team2_name = team2Name
    match.id = match_id
    return true

  populateCompetition: (metaData, callback) ->
    this.loadFromServer "/competition" + this.PROXY_PREFIX + "?id=" + metaData.id, #      "/competition" + metaData.id
      successCB: (json) =>
        matches = json.payload
        this.competitions[metaData.id] = matches
        this.populateMatch(metaData, id, match) for id,match of matches
        this.populateByes(metaData.id, metaData.nRounds)
        this.bindEvents(metaData.id)
        if callback?
          callback()
        return true
      failureCB: (xhr, status) =>
        this.errorDialog("Failed to load competition: " + metaData.name)
        return false
      loadMaskId: "div#comp_" + metaData.id
    return true


  setEndDates: (tournament) ->
    for id,compDates of tournament
      headers = jQuery("div#comp_#{ id } th.roundtitle")
      for header,i in headers
        round = compDates.nRounds - i - 1
        endDateStr = compDates.rounds[round]
        endDate = new Date(parseInt(endDateStr.substring(0,4)), parseInt(endDateStr.substring(5,7))-1, parseInt(endDateStr.substring(8,10)))
        endDateStr = jQuery.datepicker.formatDate("D d M", endDate)
        header.innerHTML += "<br>[#{ endDateStr }]"
    return true

        
  getActiveTabIndex: () ->
    return jQuery("#tabs").tabs("option", "active")


  ensureSufficientScores: (evt, ui) ->
    if this.ignore_change_events
      return
    id = evt.target.id
    tokens = id.split("_")
    set = parseInt(tokens[1].replace("score", ""))
    max_invisible_rows = 4-set
    invisible_rows = jQuery("table.score_entry tr:hidden")
    nchanges = Math.max(0, invisible_rows.length - max_invisible_rows)
    i = 0
    while i < nchanges
      invisible_rows.eq(i).css("display", "")
      ++i
    return true

  updateValidationTips: (t) ->
      tips = jQuery("div#score-entry-form p.validateTips")
      if t?
        tips      
          .text( t )
          .addClass( "ui-state-error" )
          .show()
        setTimeout(
          () -> 
            tips.removeClass( "ui-state-error", 1500 )
          500
        )
      else
        tips
          .text("Please enter match scores.")
          .removeClass( "ui-state-error")
        jQuery("div#score-entry-form input").removeClass( "ui-state-error" )

  showScoreEntryDialog: (choices) ->
    try
      # reset all the form fields:
      this.ignore_change_events = true
      comp = this.getActiveTabIndex() + 1
      scoreform = jQuery("div#score-entry-form")
      scoreform.find("input[name='tournament_id']")[0].value = comp
      scoreform.find("input[name='login_id']")[0].value    = jQuery.cookie("login_id") or ""
      scoreform.find("input[name='login_token']")[0].value = jQuery.cookie("login_token") or ""
      opponentsCombo = scoreform.find("select#walkover_result")[0]
      clearOpponentsCombo = () ->
        while (opponentsCombo.options.length > 0)
          opponentsCombo.options.remove(opponentsCombo.options.length-1)
      addOpponent = (text, value) ->
        newopt = document.createElement("option")
        newopt.text = text
        newopt.value = value
        try
         opponentsCombo.add(newopt, null)
        catch ex
          opponentsCombo.add(newopt, opponentsCombo.options[null])
        return true
      clearOpponentsCombo()
      this.updateValidationTips()
      headers = scoreform.find("table.score_entry th")
      headers[1].innerHTML = ""
      headers[2].innerHTML = ""
      matchName = scoreform.find("input#matchselector") 
      matchName[0].value = ""
      radios = scoreform.find("input[type='radio']")
      radios[0].checked = true
      this.onResultTypeChanged(radios[0])
      scoreform.find("table.score_entry td input").spinner("value", 0)
      scoreform.find("table.score_entry tr.score_row").slice(1).css("display", "none")
      unless choices?
        thisComp = this.competitions[comp]
        ids = (parseInt(id) for id,m of thisComp)
        ids.sort((lhs,rhs) -> lhs - rhs)
        choices = (thisComp[id] for id in ids)
      displayChoices = ("#{m.team1_name} vs #{m.team2_name}" for m in choices) 
      onChange = (evt, ui) =>
        idx = displayChoices.indexOf(matchName[0].value)
        if idx >= 0
          matchName.removeClass("ui-state-error")
          this.updateValidationTips()
          match = choices[idx]
          clearOpponentsCombo()
          addOpponent(match.team1_name, match.Team1_Player1_Id)
          addOpponent(match.team2_name, match.Team2_Player1_Id)
          scoreform.find("input[name='match_id']")[0].value = match.id
          scoreform.find("input[name='player1_id']")[0].value = match.Team1_Player1_Id
          scoreform.find("input[name='player2_id']")[0].value = match.Team2_Player1_Id
          headers[1].innerHTML = match.team1_name
          headers[2].innerHTML = match.team2_name
      matchName.autocomplete
        source: displayChoices
        change: onChange
        select: onChange
      if choices.length == 1
        matchName[0].value = displayChoices[0]
        onChange()
      jQuery("div#score-entry-form" ).dialog( "open" )
    finally
      this.ignore_change_events = false
    return true

  refresh: (refreshAll, callback) ->
    if refreshAll?
      comps = this.COMP_METAS
    else
      activeIndex = this.getActiveTabIndex()   
      comps = [this.COMP_METAS[activeIndex]]
    for c in comps
      this.populateCompetition(c)
      if callback?
        callback(c) 
    return true

  onLoginButton: (callback) ->
    login_id = jQuery("div#score-login-form input#login_id").val()
    login_pw = jQuery("div#score-login-form input#login_pw").val()
    jQuery.cookie("login_id", login_id)
    token = MD5(login_pw)
    jQuery.cookie("login_token", token)
    scoreform = jQuery("div#score-entry-form")
    scoreform.find("input[name='login_id']")[0].value    = login_id
    scoreform.find("input[name='login_token']")[0].value = token
    jQuery("div#score-login-form").dialog("close")
    callback()

  onResultTypeChanged: (cmp) ->
    if cmp.value == "walkover"
      jQuery("div#score-entry-form p#walkover_input").show()      
      jQuery("div#score-entry-form table.score_entry").hide()      
    else
      jQuery("div#score-entry-form p#walkover_input").hide()      
      jQuery("div#score-entry-form table.score_entry").show()      
    return true

    
  onResize: () ->
    activeCompetition = this.compContainerCache[this.getActiveTabIndex()]
    fullWidth = activeCompetition.container.width()  - this.COMP_PADDING
    fixedWidth = 0
    for i in [0..activeCompetition.spacers.length-1]
      fixedWidth += activeCompetition.spacers.eq(i).width() + 2 # width() is off by 2 - border spacing?
    playerWidth = Math.floor (fullWidth - fixedWidth) / activeCompetition.meta.nRounds
#    console.log("comp: #{activeCompetition.id} full: #{ fullWidth }, fixed: #{fixedWidth}, player: #{ playerWidth}")
    activeCompetition.container.find("td.player").css("max-width", "#{ Math.max(playerWidth, this.MIN_WIDTH) }px")
    return true
    
    
  onRefreshButton: () ->
    this.refresh(false)


  onEditButton: () ->
    this.showScoreEntryDialog()

  onScoreDeleteButton: () ->
    systemfields = jQuery("div#score-entry-form form input[type='hidden']")
    formfields = {}
    systemfields.each (idx, elt) ->
      formfields[this.name] = this.value

    jQuery("div#score-entry-form").dialog("close")      

    jQuery.ajax(
      url: this.BASE_URL + "/match" + this.PROXY_PREFIX
      type: "DELETE"
      data: formfields
      error:  (xhr, status) =>
        this.errorDialog("Unable to delete match<br>Status: #{ xhr.statusText }<br>Reason: #{ xhr.responseText }")
      success: (xhr, status) =>
        this.clearCompetition(formfields.tournament_id)
        this.refresh()
    )

  onScoreSubmitButton: () ->
    systemfields = jQuery("div#score-entry-form form input[type='hidden']")
    userfields   = jQuery("div#score-entry-form form :input").not(":hidden")

    tournament_id = systemfields.filter("[name='tournament_id']").val()
    match_id      = systemfields.filter("[name='match_id']").val()
    player1_id    = systemfields.filter("[name='player1_id']").val()
    player2_id    = systemfields.filter("[name='player2_id']").val()
    login_id      = systemfields.filter("[name='login_id']").val()
    login_token   = systemfields.filter("[name='login_token']").val()

    if player1_id == "" or player2_id = "" or match_id == "" or tournament_id == ""
      userfields.filter("#matchselector").addClass( "ui-state-error" )
      this.updateValidationTips("Please specify a Match")
      return false
    walkover_result = userfields.filter("[name='walkover_result']").val()
    if walkover_result?
      if walkover_result == player1_id
        scores = [[0, -1]]     
      else
        scores = [[-1, 0]]    
    else
      scores = ([userfields.filter("[name='team1_score#{ i }']").val(), userfields.filter("[name='team2_score#{ i }']").val()] for i in [1..6])
    result = this.findWinner(scores)
    if result.wins[0] == result.wins[1]
      userfields.filter("input.ui-spinner-input").addClass( "ui-state-error" )
      this.updateValidationTips("Please check results - cannot enter a draw")
      return false

    formfields = {}
    systemfields.each((idx, elt) -> formfields[this.name] = this.value)
    userfields.each((idx, elt) -> formfields[this.name] = this.value)

    complete = () => 
      jQuery.ajax(
        url: this.BASE_URL + "/match" + this.PROXY_PREFIX
        type: "POST"
        data: formfields
        error:  (xhr, status) =>
          if (xhr.status == 403)
            systemfields.filter("[name='login_token']").val("")
          this.errorDialog("Unable to save match result<br>Status: #{ xhr.statusText }<br>Reason: #{ xhr.responseText }")
        success: (xhr, status) =>
          jQuery("div#score-entry-form").dialog("close")              
          this.refresh()
      )

    if login_id == "" or login_token == ""
      loginform = jQuery("div#score-login-form")
      loginform.on("dialogclose", () => this.onLoginButton(complete))
      loginform.dialog("open")
    else
      complete()

      
  onReady: () ->

    # tabify the competition divs and display them:
    jQuery( "#tabs" )
      .tabs(
        beforeActivate: (evt) =>
          this.onResize(evt);
      )
      .removeClass("initiallyHidden")

    # setup event handlers for the buttons, and display them:
    jQuery("button").button().click((event) => 
      # Chrome has the target as a span, FF directly as the button
      elt = event.target
      while not elt.id
        elt = elt.parentElement
      action = "on" + elt.id
      func = WSRC[action] # get the function in our namespace with the same name as the button's id 
      func.apply(this)    # and call it
    ).removeClass("initiallyHidden")

    jQuery("div#score-entry-form").dialog
      autoOpen: false
      show: "blind"
      width: 450
      modal: true
      closeOnEscape: true
      buttons: 
#        "Delete": () =>
#          this.onScoreDeleteButton()
        "Submit": () =>
          this.onScoreSubmitButton()
        Cancel: () -> 
          jQuery( this ).dialog( "close" )
      close: () ->

    jQuery("div#score-login-form").dialog
      autoOpen: false
      show: "blind"
      width: 350
      modal: true
      closeOnEscape: true
      close: () ->
      buttons:
        "Login": () -> jQuery( this ).dialog( "close" )
        
    jQuery("div#score-entry-form table.score_entry td input").spinner
      change: (evt, ui) =>
        this.updateValidationTips()
        this.ensureSufficientScores(evt, ui)
        
    jQuery("div#score-entry-form input#matchselector").autocomplete

    # setup a cache of data for each competition, with cached jQueries
    containers =  jQuery("div.x-competition")
    this.compContainerCache =  for i in [0..containers.length-1] 
      do (i) =>
        container = containers.eq(i)
        return {
          id: container[0].id
          meta: this.COMP_METAS[i]
          container: container 
          spacers: container.find("td.spacercalc")
        }
    jQuery(window).resize (evt) =>
      this.onResize(evt)
    
    # helper to load from the restful store 
    loadGlobal = (url, callback) =>
      this.loadFromServer url, 
        successCB: (json) =>
          callback(json.payload) 
          return true
        failureCB: (xhr, status) => 
          this.errorDialog("ERROR: Failed to load data from #{ url }")
          return true
        loadMaskId: "body" 
      return true
      
    loadGlobal("/tournament" + this.PROXY_PREFIX, (payload) =>
      this.setEndDates(payload)
      loadGlobal("/players" + this.PROXY_PREFIX, (payload) =>
        this.players = payload
        # now the other loads are complete, fetch and load all competitions
        this.refresh(true, (comp) =>
          if comp == this.COMP_METAS[0]
            this.onResize()
        ) 
        return true
      )
      return true
    )

    return true



