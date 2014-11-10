
unless window.assert?
  window.assert = (condition, message) ->
    unless condition 
      throw message || "Assertion failed"
      
window.WSRC =

  toggle: (onid, offid) ->
    jQuery("##{ onid }").css("display", "")
    jQuery("##{ offid }").css("display", "none")

  league_config: null
  league_results: null

  findMatching: (list, id, id_key) ->
    unless id_key?
      id_key = "id"
    for l in list
      if l[id_key] == id
        return l
    return null

  ##
  # Remove non-empty items from the selector and replace with the given list
  ## 
  bulkAdd: (selector, list) ->
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
  showErrorDialog: (msg) ->
    jQuery("#errorPopupDialog div[role='main'] h3").html(msg)
    jQuery("#errorPopupDialog").popup()
    jQuery("#errorPopupDialog").popup("open")
    return true

  ##
  # Helper function for Ajax requests back to the server.
  # OPTS is an object containing:
  #  successCB - function to call back when successful
  #  failureCB - function to call back when there is an error
  ## 
  loadFromServer: (url, opts) ->
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
  # Transition to the league detail page - needs setup for the league from which it was opened
  ##
  openBoxDetailDialog: (id) ->
    id = id.replace("link-", "")
    results_config = this.findMatching(this.league_results.competitions_expanded, parseInt(id), "id")

    # setup page and inputs
    dialogdiv = jQuery("div#boxDetailDialog")
    dialogdiv.find("div h2").text(results_config.name) # page title

    setupPointsTable = () =>
      tablebody = dialogdiv.find("table#league-table tbody")

      # remove existing rows
      tablebody.find("tr").remove()
  
      newTotals = () -> {p: 0, w: 0, d: 0, l: 0, f: 0, a: 0, pts: 0}
      
      # sum up the totals for each result
      player_totals = {}
      if results_config?
        for r in results_config.matches
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
      for player in results_config.players
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

      if results_config?.matches?
        results = results_config.matches
        results.sort((l,r) ->
          l.timestamp > r.timestamp
        )
        id2NameMap = {} 
        for p in results_config.players
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
      players = (p for p in results_config.players)
      players.sort()
      this.bulkAdd(form.find("select#player1"), players)
      this.bulkAdd(form.find("select#player2"), players)

    setupPointsTable()
    setupResults()
    setupAddScoreDialog()
    dialogdiv.find("div#add-change-div").collapsible().collapsible("expand")
#    jQuery.mobile.changePage("#boxDetailDialog")

    return null

  ##
  # Setup the input form when one of the players is selected in the add score section
  ##
  playerSelected: (selector_id) ->
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
      this.bulkAdd(otherselector, ({id:p[0], full_name:p[1]} for p in players))

    checkBothPlayersSelected = () =>
      selector1 = form.find("select#player1")
      selector2 = form.find("select#player2")
      unless (selector1.val() == "" or selector2.val() == "")
        # we have names for both players; enable the other inputs:
        form.find("input[type='radio']").checkboxradio('enable')
        form.find("table td input").textinput("enable")
        # and add players to the walkover result combo
        selects = (form.find("select##{ p }")[0] for p in ['player1', 'player2'])
        this.bulkAdd(form.find("select#walkover_result"), ({id:e.options[e.selectedIndex].value, full_name:e.options[e.selectedIndex].text} for e in selects))

    checkBothPlayersSelected()
    return null

  # ##
  # # Draw the boxes on the main page once the box config is available.
  # ##
  # createBoxes: (league_config) ->
  #   maxplayers = (b.players.length for b in league_config.boxes).reduce (x,y) -> Math.max(x,y)

  #   # helper method to create a table DOM for the box from config
  #   createBoxTable = (box_config) ->
  #     tbl = jQuery("<table data-role='table' data-mode='' id='table-#{ box_config.id }' class='boxes ui-corner-all ui-table'>")
  #     html = "<thead><tr><th colspan='2'></th>" +
  #       ("<td class='ui-bar-a'>#{ i }</td>" for i in [1..maxplayers]).join("") +
  #       "<td class='ui-bar-a'>&#x3a3;</td>" +
  #       "</tr></thead><tbody>"
  #     tbl.append(html)
  #     rows = []
  #     for i in [1..maxplayers]
  #       player = box_config.players[i-1]
  #       if player?
  #         playerId = "id='player-#{ player.id }'"
  #       html = "<tr #{ playerId }><th>#{ player.name ? '' }</td><td class='ui-bar-a'>#{ i }</td>"
  #       for j in [1..maxplayers]
  #         if j == i
  #           html += "<td class='ui-bar-a'> </td>"
  #         else
  #           html += "<td> </td>"
  #       html += "<td class='score_total'> </td>"
  #       rows.push(html)
  #     tbl.append(rows.join("") + "</tbody>")
  #     return tbl

  #   maindiv = jQuery("body div#boxes div[role='main']")

  #   # step through the config and create tables wrapped in
  #   # grid-controlling divs. For doublecolumn setups, we cache the
  #   # wrapper div until the second iteration and only add it at the end.
  #   wrapperdiv = null
  #   for box_config in league_config.boxes
  #     doublecolumn = box_config.doublecolumn?
  #     secondcolumn = doublecolumn and wrapperdiv?
  #     unless secondcolumn
  #       colspec = doublecolumn and "double" or "single"
  #       wrapperdiv = jQuery("<div class='ui-grid-a boxes-wrapper boxes-wrapper-#{ colspec }column'>")
  #       wrapperdiv.trigger("create")
  #     extraclasses = ""
  #     if doublecolumn
  #       extraclasses = "boxes-" + (secondcolumn and "second" or "first") + "column ui-block-" + (secondcolumn and "b" or "a")
  #     boxdiv = jQuery("<div class='ui-corner-all custom-corners boxes #{ extraclasses }'>")
  #     boxdiv.append("<div class='ui-bar ui-bar-a' data-role='header' data-position='inline'><h2>#{ box_config.name }</h2><div><a id='link-#{ box_config.id }' href='#' onclick='WSRC.onBoxActionClicked(this); return false;' class='ui-btn ui-icon-gear ui-corner-all ui-mini ui-btn-right ui-btn-icon-right'>Edit</a></div></div>")
  #     tablediv = jQuery("<div class='ui-body ui-body-a'>")
  #     tablediv.append(createBoxTable(box_config))
  #     boxdiv.append(tablediv)
  #     boxdiv.trigger("create") # ask JQM to do style the new box
  #     wrapperdiv.append(boxdiv)
  #     if not doublecolumn or secondcolumn
  #       maindiv.append(wrapperdiv)
  #     unless doublecolumn and not secondcolumn
  #       wrapperdiv = null
  #   return null

  refreshScores: (results) ->
    getPlayerIndex = (table, playerId) ->
      table.find("tr#player-#{ playerId } :nth-child(2)").text()
    getTableCell = (table, player1Id, player2Id) ->
      p2idx = getPlayerIndex(table, player2Id)
      offset = parseInt(p2idx) + 2
      table.find("tr#player-#{ player1Id } :nth-child(#{ offset })")
      
    for box in results.competitions_expanded
      jbox = jQuery("table#table-#{ box.id }")
      totals = {}
      addScore = (player, score) ->
        unless player of totals
          totals[player] = 0
        totals[player] += score
      for result in box.matches
        getTableCell(jbox, result.player1, result.player2).text(result.points[0])
        getTableCell(jbox, result.player2, result.player1).text(result.points[1])
        addScore(result.player1, result.points[0])
        addScore(result.player2, result.points[1])
      jbox.find("tbody tr").each((idx,elt) ->
        if elt.id?
          elt.lastElementChild.textContent = totals[elt.id.replace("player-", "")] ? "0"
      )
    return true
      
  onBoxActionClicked: (link) ->
    this.openBoxDetailDialog(link.id)

  onPlayerSelected: (selector) ->
    this.playerSelected(selector.id)

  loadBoxResults: (id) ->
    url = "/comp_data/competitiongroup/#{ id }?expand=1"
    this.loadFromServer(url,
      successCB: (results) =>
        this.league_results = results
        this.refreshScores(results)
        return true
      failureCB: (xhr, status) => 
        this.showErrorDialog("ERROR: Failed to load data from #{ url }")
        return false
    )


`if ( 'function' !== typeof Array.prototype.reduce ) {
  Array.prototype.reduce = function( callback /*, initialValue*/ ) {
    'use strict';
    if ( null === this || 'undefined' === typeof this ) {
      throw new TypeError(
         'Array.prototype.reduce called on null or undefined' );
    }
    if ( 'function' !== typeof callback ) {
      throw new TypeError( callback + ' is not a function' );
    }
    var t = Object( this ), len = t.length >>> 0, k = 0, value;
    if ( arguments.length >= 2 ) {
      value = arguments[1];
    } else {
      while ( k < len && ! k in t ) k++; 
      if ( k >= len )
        throw new TypeError('Reduce of empty array with no initial value');
      value = t[ k++ ];
    }
    for ( ; k < len ; k++ ) {
      if ( k in t ) {
         value = callback( value, t[k], k, t );
      }
    }
    return value;
  };
}
`
