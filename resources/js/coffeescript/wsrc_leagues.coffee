
window.WSRC_leagues =

  get_competition_for_id: (box_id) ->
    box_id = parseInt(box_id)
    wsrc.utils.list_lookup(this.competitiongroup_data.competitions_expanded, box_id)

  get_player_config: (box_id, player_id) ->
    players = this.get_competition_for_id(box_id).players
    player_id = parseInt(player_id)
    wsrc.utils.list_lookup(players, player_id)

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
        for p in this_box_config.entrants
          id2NameMap[p.player.id] = p.player.full_name
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
      wsrc.utils.set_on_and_off('score-entry-input', 'walkover_input')
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

    setupResults()
    setupAddScoreDialog()
    dialogdiv.find("div#add-change-div").collapsible().collapsible("expand")
    return null

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
    for entrant in this_box_config.entrants
      player = entrant.player
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
      entrants = this_box_config.entrants
      entrants.sort (lhs, rhs) ->
        lhs.ordering - rhs.ordering
      while idx < entrants.length
        playerIdToIndexMap[entrants[idx].player.id] = idx
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

        
