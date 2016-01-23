################################################################################
# Model - contains a local copy of the member databases
################################################################################

class WSRC_boxes_model
   
  constructor: (@member_map, @source_competitiongroup) ->

  get_source_boxes: () ->
    return @source_competitiongroup.competitions_expanded


################################################################################
# View - JQuery interactions with the html
################################################################################

class WSRC_boxes_view

  constructor: (@callbacks) ->
    @is_admin_view = $("#source_boxes").length == 1

  populate_box: (box, max_players, points_map) ->
    table_body = $("#box_#{ box.id } table.boxtable tbody")
    table_body.children().remove()
    player_id_to_index_map = {}
    rows = []
    idx = 0
    for player_spec in box.entrants
      player = player_spec.player
      name = player.full_name
      if @is_admin_view
        name += " [#{ player.id }]"
      player_id_to_index_map[player.id] = idx
      current_user_cls = ''
      block_cls = 'ui-bar-a block'
      jrow = $("<tr data-id='#{ player.id }'><th class='#{ current_user_cls } text player'>#{ name }</th><th class='#{ block_cls }'>#{ idx+1 }</th></tr>")
      row = []
      rows.push(row)
      for j in [0...max_players]
        if idx == j
          jcell = $("<td class='#{ block_cls } number'></td>")
        else
          jcell = $("<td class='number'></td>")
        jrow.append(jcell)
        row.push(jcell)
      jrow.append("<td class='number'>#{ points_map[player.id] }</td>")
      table_body.append(jrow)
      idx++
    for match in box.matches
      p1 = player_id_to_index_map[match.team1_player1]
      p2 = player_id_to_index_map[match.team2_player1]
      rows[p1][p2].text(match.points[0])
      rows[p2][p1].text(match.points[1])
        
  populate_points_table: (box, max_players, points_totals, id_to_player_map) ->
    table_body = $("#box_#{ box.id } table.leaguetable tbody")
    table_body.children().remove()
    for row in points_totals
      player = id_to_player_map[row.id]
      current_user_cls = ''
      name = player.full_name
      if @is_admin_view
        name += " [#{ player.id }]"
      tr = "<tr data-id='#{ player.id }'><th class='text player'>#{ name }</th><td class='number'>#{ row.p }</td><td class='number'>#{ row.w }</td><td class='number'>#{ row.d }</td><td class='number'>#{ row.l }</td><td class='number'>#{ row.f }</td><td class='number'>#{ row.a }</td><td class='number'>#{ row.pts }</td></tr>"
      table_body.append(tr)

      
  set_view_type: (view_type) ->
    if view_type == "tables"
      $("table.boxtable").hide()
      $("table.leaguetable").show()
    else
      $("table.leaguetable").hide()
      $("table.boxtable").show()

  make_id_filter: (id) ->
    return (idx, elt) ->
      $(elt).data("id") == id
    
  set_source_player_ghost: (id) ->
    rows = $("#source_boxes tr").filter(@make_id_filter(id))
    draggables = rows.find("th.player:not(.ui-draggable-dragging)")
    draggables.css("opacity", 0.3)
    return draggables
    
  revert_source_player_ghost: (id) ->
    rows = $("#source_boxes tr").filter(@make_id_filter(id))
    draggables = rows.find("th.player")
    draggables.css("opacity", 1.0)
    return draggables
    
    

################################################################################
# Controller - initialize and respond to events
################################################################################

class WSRC_boxes

  constructor: (@model) ->
    max_players = 0
    @view = new WSRC_boxes_view()
    for box in @model.get_source_boxes()
      max_players = Math.max(max_players, box.entrants.length)
    for box in @model.get_source_boxes()      
      points_table = @get_points_totals(box)
      points_map = {}
      for row in points_table
        points_map[row.id] = row.pts
      @view.populate_box(box, max_players, points_map)
      @view.populate_points_table(box, max_players, points_table, @model.member_map)

    view_radios = $("input[name='view_type']")
    view_radios.on("change", (evt) =>
      @handle_display_type_change(evt)
    )

    $("input.hasDatePicker").datepicker
      dateFormat: "yy-mm-dd"

    me = this
    if @view.is_admin_view
      $("#source_boxes th.player").draggable(
        opacity: 0.7
        helper:  "clone"
        revert:  "invalid"
        start:   (event, ui) => @handle_source_player_drag_start(event, ui)
        stop:    (event, ui) => @handle_source_player_drag_stop(event, ui)
      )
      players = ("#{ player.full_name } [#{ player.id }]" for id,player of @model.member_map)  
      $("#target_boxes input.player").autocomplete(
        source: players
        select: (event, ui) => @handle_target_autocomplete_select(event, ui)
        change: (event, ui) => @handle_target_autocomplete_change(event, ui)
      ).droppable(
        hoverClass: "ui-state-hover",
        accept: ".player",
        drop: ( event, ui ) ->
          me.handle_source_player_dropped(event, ui, $(this))
      )
      $("#target_boxes tbody").sortable(
        handle: ".handle"
        containment: "parent"
      )
      $("button.remove").button(
        text: false,
        icons:
          primary: "ui-icon-close"
      ).on("click", (evt, ui) => @handle_target_remove_button_click(evt, ui))

  get_points_totals: (this_box_config) ->
    newTotals = (player_id) -> {id: player_id, p: 0, w: 0, d: 0, l: 0, f: 0, a: 0, pts: 0}
    player_totals = {}
    for e in this_box_config.entrants
      player = e.player
      player_totals[player.id] = newTotals(player.id)
    for r in this_box_config.matches
      for i in [1..2]
        player_id = r["team#{ i }_player1"]
        totals = player_totals[player_id]
        unless totals?
          totals =  player_totals[player_id] = newTotals(player_id)
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
    player_totals = (totals for id,totals of player_totals)
    player_totals.sort((l,r) ->
      result = r.pts - l.pts
      if result == 0
        result = (r.f-r.a) - (l.f-l.a)
        if result == 0
          result = r.full_name < l.full_name
      result
    )
    return player_totals

  collect_target_league_players: (ignored_input) ->
    tables = $("#target_boxes table")
    result = {}
    tables.each (idx, table) =>
      player_list = []
      league_name = $(table).find("caption").text()
      $(table).find("tbody tr input").each (idx1, input) =>
        unless ignored_input == input
          id = @scrape_player_id($(input).val())
          if id
            player_list.push(id)
      if player_list.length > 0
        result[league_name] = player_list
    return result

  scrape_player_id: (str) ->
    unless str
      return null
    id = str.substring(str.lastIndexOf("[")+1, str.lastIndexOf("]"))
    id = wsrc.utils.to_int(id)
    if isNaN(id)
      return  null
    return id

  handle_target_remove_button_click: (evt, ui) ->
    button = $(evt.target)
    input = button.parents("tr").find("input")
    player_str = input.val()
    input.val("")
    id = @scrape_player_id(player_str)
    if id
      draggables = @view.revert_source_player_ghost(id)
      draggables.draggable("enable")

  handle_target_autocomplete_select: (evt, ui) ->
    player_str = ui.item.value
    player_id = @scrape_player_id(player_str)
    for league, players of @collect_target_league_players(evt.target)
      if players.indexOf(player_id) >= 0
        input = $(evt.target).parents("tr").find("input")
        alert("ERROR: #{ player_str } is already in box \"#{ league }\"")
        input.val("")
        evt.stopPropagation()
        evt.preventDefault()
        return false
    draggables = @view.set_source_player_ghost(player_id)
    draggables.draggable("disable")

  handle_target_autocomplete_change: (evt, ui) ->
    input = $(evt.target).parents("tr").find("input")
    player_str = input.val()
    player_id = @scrape_player_id(player_str)
    unless player_id
        alert("ERROR: Cannot get player ID from \"#{ player_str }\"")
        input.val("")
        evt.stopPropagation()
        evt.preventDefault()
        return false
    

  handle_source_player_dropped: (evt, ui, target) ->
    source = ui.draggable
    if source.hasClass("player")
      id = wsrc.utils.to_int(source.parents("tr").data("id"))
      target.val(ui.draggable.text())
      draggables = @view.set_source_player_ghost(id)
      draggables.draggable("disable")
            
  handle_source_player_drag_start: (evt, ui) ->
    source = $(evt.target)
    id = wsrc.utils.to_int(source.parents("tr").data("id"))
    @view.set_source_player_ghost(id)

  handle_source_player_drag_stop: (evt, ui) ->
    source = $(evt.target)
    unless source.draggable("option").disabled
      id = wsrc.utils.to_int(source.parents("tr").data("id"))
      @view.revert_source_player_ghost(id)

  handle_display_type_change: (evt) ->
    view_radios = $("input[name='view_type']")
    view_type = view_radios.filter(":checked").val()
    @view.set_view_type(view_type)


  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: (player_list, source_competitiongroup) ->
    model = new WSRC_boxes_model(player_list, source_competitiongroup)
    @instance = new WSRC_boxes(model)


window.wsrc.boxes = WSRC_boxes
 
