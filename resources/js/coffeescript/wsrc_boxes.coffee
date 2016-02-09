################################################################################
# Model - contains a local copy of the member databases
################################################################################

class WSRC_boxes_model
   
  constructor: (@member_map, competition_groups, @source_competitiongroup) ->
    @competition_group_map = wsrc.utils.list_to_map(competition_groups, 'id')
    @current_competition_groups = []
    @new_competition_groups = []
    for group in competition_groups
      if group.comp_type == "wsrc_boxes"
        status = group.status
        if status == "empty" or status == "not_started"
          @new_competition_groups.push(group)
        else if status == "active" or status == "complete"
          @current_competition_groups.push(group)



################################################################################
# View - JQuery interactions with the html
################################################################################

class WSRC_boxes_view

  constructor: (@callbacks) ->
    @ghost_opacity = 0.4    
    @is_admin_view = $("#source_boxes").length == 1

    source_container = $("#source_boxes")
    source_container.find("input.player").val("")
    @source_container_map = {}
    do_mapping = (container, map) =>
      tables = container.find("table")
      tables.each (idx, elt) =>
        box = $(elt)
        name = @get_table_name(box)
        map[name] = box.parent()
    do_mapping(source_container, @source_container_map)

    target_container = $("#target_boxes")
    if target_container.length == 1
      @target_container_map = {}
      do_mapping(target_container, @target_container_map)

  get_table_name: (jtable) ->
    return jtable.find("caption").contents()[0].nodeValue

  get_player_name: (player) ->
    name = player.full_name
    if @is_admin_view
      name += " [#{ player.id }]"
    return name

  populate_box: (box, max_players, points_table) ->
    points_map = {}
    for row in points_table
      points_map[row.id] = row.pts
    container = @source_container_map[box.name]
    table_body = container.find("table.boxtable tbody")
    table_body.children().remove()
    player_id_to_index_map = {}
    rows = []
    idx = 0
    for player_spec in box.entrants
      player = player_spec.player
      name = @get_player_name(player)
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
    container = @source_container_map[box.name]
    table_body = container.find("table.leaguetable tbody")
    table_body.children().remove()
    for row in points_totals
      player = id_to_player_map[row.id]
      current_user_cls = ''
      name = player.full_name
      if @is_admin_view
        name += " [#{ player.id }]"
      tr = "<tr data-id='#{ player.id }'><th class='text player'>#{ name }</th><td class='number'>#{ row.p }</td><td class='number'>#{ row.w }</td><td class='number'>#{ row.d }</td><td class='number'>#{ row.l }</td><td class='number'>#{ row.f }</td><td class='number'>#{ row.a }</td><td class='number'>#{ row.pts }</td></tr>"
      table_body.append(tr)

  populate_new_table: (comp) ->
    container = @target_container_map[comp.name]
    container.data("id", comp.id)
    inputs = container.find("input.player")
    inputs.val("")
    idx = 0
    for entrant in comp.entrants
      inputs.eq(idx).val(@get_player_name(entrant.player))
      @set_source_player_ghost(entrant.player.id)
      ++idx

  clear_new_tables: () ->
    for id, container of @target_container_map
      container.data("id", null)
      inputs = container.find("input.player")
      inputs.val("")

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

  relocate_player: (player, table_name, index) ->
    target_table = @target_container_map[table_name]
    target = target_table.find("input").eq(index)
    if target.val() == ""
      target.val(@get_player_name(player))
      draggables = @set_source_player_ghost(player.id)
      draggables.draggable("disable")
        
  set_source_player_ghost: (id) ->
    rows = $("#source_boxes tr").filter(@make_id_filter(id))
    draggables = rows.find("th.player:not(.ui-draggable-dragging)")
    draggables.css("opacity", @ghost_opacity)
    return draggables
    
  revert_source_player_ghost: (id) ->
    rows = $("#source_boxes tr")
    if id
      rows = rows.filter(@make_id_filter(id))
    draggables = rows.find("th.player")
    draggables.css("opacity", 1.0)
    return draggables

  hide_source_leagues: () ->
    $("#source_boxes div.table-wrapper").hide()
        
  show_source_league: (league) ->
    @source_container_map[league.name].show()    

  show_new_league_dialog: () ->
    jqdialog = $("#new_league_form_dialog")
    jqdialog.dialog(
      width: 450
      height: 100
      autoOpen: false
      model: true
      dialogClass: "new_member_form_dialog"
    )
    jqdialog.dialog("open")

    

################################################################################
# Controller - initialize and respond to events
################################################################################


class WSRC_boxes

  constructor: (@model) ->
    @view = new WSRC_boxes_view()
    @populate_source_competition_group(@model.source_competitiongroup)

  populate_source_competition_group: (competition_group) ->
    max_players = 0
    leagues = competition_group.competitions_expanded
    for league in leagues
      max_players = Math.max(max_players, league.entrants.length)
    @view.hide_source_leagues()
    for league in leagues
      points_table = @get_points_totals(league)
      @view.populate_box(league, max_players, points_table)
      @view.populate_points_table(league, max_players, points_table, @model.member_map)
      @view.show_source_league(league)

    view_radios = $("input[name='view_type']")
    view_radios.on("change", (evt) =>
      @handle_display_type_change(evt)
    )

  fetch_competition_group: (group, callback) ->
    jqmask  = $("#maskdiv")
    jqmask.css("z-index", "1")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      successCB: (data, status, jq_xhr) =>
        jqmask.unmask()
        jqmask.css("z-index", "-1")
        callback(data)
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        jqmask.css("z-index", "-1")
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to fetch data for '#{ group.name }'.")
    jqmask.mask("Fetching data for \'#{ group.name }\'...")
    wsrc.ajax.ajax_bare_helper("/data/competitiongroup/#{ group.id }?expand=1", null, opts, "GET")
    
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

  @onReady: (player_list, source_competitiongroup, competition_groups) ->
    model = new WSRC_boxes_model(player_list, source_competitiongroup, competition_groups)
    @instance = new WSRC_boxes(model)

class WSRC_boxes_admin extends WSRC_boxes

  constructor: (model) ->
    super model
    me = this

    # save button
    @view.target_save_button = $("#target_boxes button[value='save']")
    @view.target_save_button.on "click", () =>
      @handle_target_save_click()
    $(window).bind 'keydown', (event) =>
      if (event.ctrlKey) 
        if String.fromCharCode(event.which).toLowerCase() == 's'
          event.preventDefault();
          @handle_target_save_click()
          
    # setup autocomplete list for target inputs, and also make them droppable
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

    # allow them to be drag-sorted:
    $("#target_boxes tbody").sortable(
      handle: ".handle"
      containment: "parent"
      change: () =>
        @mark_save_required()
    )

    # setup handler for cancel button on each input
    $("#target_boxes button.remove").button(
      text: false,
      icons:
        primary: "ui-icon-close"
    ).on("click", (evt, ui) => @handle_target_remove_button_click(evt, ui))
    
    # Now set up the new league date selector...
    @view.target_end_date = $("#target_boxes input[name='end_date']")
    @mark_save_required(false)

    # On initialization fetch the latest unstarted comp group
    if @model.new_competition_groups.length > 0
      group = @model.new_competition_groups[0]
      @view.target_end_date.val(group.end_date)
      @fetch_competition_group(group, @populate_target_competition_group)

    # Formatting, and mark dirty when the date changes 
    @view.target_end_date.datepicker
      dateFormat: "yy-mm-dd"
      onSelect: (dateText, inst) =>
        @mark_save_required()

    # setup the source league selector, as it is not populated by django in the admin template
    source_league_selector = $("#source_boxes select[name='league']")
    for group in @model.current_competition_groups
      opt = $("<option value='#{ group.id }'>#{ group.name }</option>")
      source_league_selector.append(opt)
      if group.id == @model.source_competitiongroup.id
        opt.prop('selected': true)
    source_league_selector.on "change", () =>
      @handle_source_league_changed(source_league_selector.val())

    # bulk action inputs:
    @view.bulk_action_selector = $("#target_boxes select[name='action']")
    @view.bulk_action_go_button = $("#target_boxes button[name='go']")
    @toggle_bulk_action()
    @view.bulk_action_selector.on "change", () =>
      @toggle_bulk_action()
    @view.bulk_action_go_button.on "click", () =>
      dispach_target = "handle_bulk_action_#{ @view.bulk_action_selector.val() }"
      @view.bulk_action_selector.val("")
      @toggle_bulk_action()
      me[dispach_target]()

    $("#source_boxes caption button.auto").button(
      icons: {primary: "ui-icon-arrowthickstop-1-e"}
      text: false
    ).on "click", (evt) =>
      table = $(evt.target).parents("table")
      @auto_populate_new_box(table)
      

    $("#target_boxes button.clear_all").button
      icons: {primary: "ui-icon-arrowreturnthick-1-w"}
      text: false

  populate_source_competition_group: (competition_group) ->
    super competition_group
    $("#source_boxes th.player").draggable(
      opacity: 1.0 - @model.ghost_opacity
      helper:  "clone"
      revert:  "invalid"
      start:   (event, ui) => @handle_source_player_drag_start(event, ui)
      stop:    (event, ui) => @handle_source_player_drag_stop(event, ui)
    )

  populate_target_competition_group: (competition_group) =>
    @view.revert_source_player_ghost()
    @view.clear_new_tables()
    id = null
    if competition_group
      id = competition_group.id
      for comp in competition_group.competitions_expanded
        @view.populate_new_table(comp)
    $("#target_boxes").data("id", id)

  auto_populate_new_box: (source_box) ->
    jtable = source_box.parents(".table-wrapper").find(".leaguetable")
    source_name = @view.get_table_name(source_box)
    other = (suffix) -> if suffix == "A" then "B" else "A"
    if source_name == "Premier"
      league_number = 0
      sibling = "Premier"
      child_1 = "League 1A"
      child_2 = "League 1B"
    else
      unless source_name.startsWith("League ")
        throw "ERROR: invalid source_name: #{ source_name }"
      league_number = wsrc.utils.to_int(source_name.slice(-2,-1))
      league_suffix = source_name.slice(-1).toUpperCase()
      if league_number == 1
        parent_1 = "Premier"
        parent_2 = null
      else
        parent_1 = "League #{ league_number-1 }#{ league_suffix }"
        parent_2 = "League #{ league_number-1 }#{ other(league_suffix) }"
      sibling = "League #{ league_number }#{ league_suffix }"
      child_1 = "League #{ league_number+1 }#{ league_suffix }"
      child_2 = "League #{ league_number+1 }#{ other(league_suffix) }"
    
    entrants = @collect_source_league_players(jtable)
    idx = 1
    while idx <= entrants.length
      entrant = entrants[idx-1]
      player = @model.member_map[entrant.player.id]
      done = false
      set_target = (target_position, target_name) =>
        if @view.relocate_player(player, target_name, target_position-1)
          @mark_save_required()
        done = true
      if idx == 1 # top position
        if league_number == 1 # in league 1, only the top gets promoted
          if league_suffix == "A"
            set_target(5, parent_1) # A -> #5
          else
            set_target(6, parent_1) # B -> #6
        else if league_number > 1 # in leagues > 1, promote vertically to #5
          set_target(5, parent_1)
      else if idx == 2 # second place, gets diagonally promoted in leagues > 1
        if league_number > 1
          set_target(6, parent_2)
      else if idx == 5 # 5th place gets demoted vertically to #1
        set_target(1, child_1)
      else if idx == 6 # 6th place gets demoted diagonally to #2
        if league_number == 0
          set_target(1, child_2)
        else
          set_target(2, child_2)
      if not done
        set_target(idx, sibling) # default - move horizontally   
      ++idx
      
        
    

  collect_source_league_players: (jtable) ->
    entrants = []
    jtable.find("tbody th.player").each (idx1, elt) =>
      id = @scrape_player_id(elt.textContent)
      if id
        entrants.push
          player:
            id: id
          ordering: idx1
    return entrants

  collect_target_league_players: (ignored_input) ->
    tables = $("#target_boxes table")
    result = {}
    tables.each (idx, table) =>
      entrants = []
      jtable = $(table)
      league_name = @view.get_table_name(jtable)
      jtable.find("tbody tr input").each (idx1, input) =>
        unless ignored_input == input
          id = @scrape_player_id($(input).val())
          if id
            entrants.push
              player:
                id: id
              ordering: idx1
      if entrants.length > 0
        result[league_name] =
          name: league_name
          entrants: entrants
          ordering: jtable.data("ordering")
    return result

  scrape_player_id: (str) ->
    unless str
      return null
    id = str.substring(str.lastIndexOf("[")+1, str.lastIndexOf("]"))
    id = wsrc.utils.to_int(id)
    if isNaN(id)
      return  null
    return id

  mark_save_required: (val) ->
    val = val != false
    @view.target_save_button.prop('disabled', not val)

  toggle_bulk_action: () ->
    disabled = @view.bulk_action_selector.val() == ''
    @view.bulk_action_go_button.prop("disabled", disabled)
        
  handle_source_league_changed: (comp_group_id) ->
    group = @model.competition_group_map[comp_group_id]
    @fetch_competition_group(group, (data) =>
      @model.source_competitiongroup = data
      @populate_source_competition_group(data)
      @view.revert_source_player_ghost()
      league_players_map = @collect_target_league_players()
      for league_name, comp_data of league_players_map
        for entrant in comp_data.entrants
          draggables = @view.set_source_player_ghost(entrant.player.id)
          draggables.draggable("disable")
    )

  handle_target_remove_button_click: (evt, ui) ->
    button = $(evt.target)
    input = button.parents("tr").find("input")
    player_str = input.val()
    input.val("")
    id = @scrape_player_id(player_str)
    if id
      draggables = @view.revert_source_player_ghost(id)
      draggables.draggable("enable")
      @mark_save_required()

  handle_target_save_click: (evt, ui) ->    
    end_date = @view.target_end_date.val()
    if end_date == ''
      alert("ERROR - no end date set\n\nPlease set the end date before saving this league.")
      return
    end_js_date = wsrc.utils.iso_to_js_date(end_date)
    comp_group =
      name: "Leagues Ending #{ wsrc.utils.js_to_readable_date_str(end_js_date) }"
      end_date: end_date
      comp_type: "wsrc_boxes"
      active: false
      competitions_expanded: []
    id = $("#target_boxes").data("id")
    if id
      comp_group.id = id
    named_league_map = @collect_target_league_players()
    for name, data of named_league_map
      data.end_date = end_date
      data.state = "not_started"
      comp_group.competitions_expanded.push(data)
      
    jqmask  = $("#maskdiv")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      completeCB: (xhr, status) ->
        jqmask.unmask()
        jqmask.css("z-index", "-1")
      successCB: (data, status, jqxhr) =>
        comp_group.id = data.id
        $("#target_boxes").data("id", comp_group.id)
        @mark_save_required(false)
      failureCB: (xhr, status, error) -> 
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to save data for '#{ comp_group.name }'.")
    
    jqmask.css("z-index", "1")
    jqmask.mask("Saving Group \'#{ comp_group.name }\'...")
    if comp_group.id?
      wsrc.ajax.ajax_bare_helper("/data/competitiongroup/#{ comp_group.id }?expand=1", comp_group, opts, "PUT")
    else
      wsrc.ajax.ajax_bare_helper("/data/competitiongroup/?expand=1", comp_group, opts, "POST")

  handle_target_autocomplete_select: (evt, ui) ->
    player_str = ui.item.value
    player_id = @scrape_player_id(player_str)
    for league, comp_data of @collect_target_league_players(evt.target)
      player_ids = (e.player.id for e in comp_data.entrants)
      if player_ids.indexOf(player_id) >= 0
        input = $(evt.target).parents("tr").find("input")
        alert("ERROR: #{ player_str } is already in box \"#{ league }\"")
        input.val("")
        evt.stopPropagation()
        evt.preventDefault()
        return false
    draggables = @view.set_source_player_ghost(player_id)
    draggables.draggable("disable")
    @mark_save_required()

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
    @mark_save_required()
    

  handle_source_player_dropped: (evt, ui, target) ->
    source = ui.draggable
    if source.hasClass("player")
      id = wsrc.utils.to_int(source.parents("tr").data("id"))
      target.val(ui.draggable.text())
      draggables = @view.set_source_player_ghost(id)
      draggables.draggable("disable")
      @mark_save_required()
            
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

  handle_bulk_action_clear: () ->
    @view.revert_source_player_ghost()
    @view.clear_new_tables()
    @mark_save_required()

  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: (player_list, competition_groups, initial_competition_group) ->
    model = new WSRC_boxes_model(player_list, competition_groups, initial_competition_group)
    @instance = new WSRC_boxes_admin(model)

    

window.wsrc.boxes = WSRC_boxes
admin = wsrc.utils.add_object_if_unset(window.wsrc, "admin")
admin.boxes = WSRC_boxes_admin
 
