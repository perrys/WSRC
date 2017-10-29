################################################################################
# Model - contains a local copy of the member databases
################################################################################

class WSRC_boxes_model
   
  constructor: (@member_map) ->


################################################################################
# View - JQuery interactions with the html
################################################################################

class WSRC_boxes_view

  constructor: (@is_admin_view) ->
    @ghost_opacity = 0.4    

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
    name = jtable.data("name")
    unless name
      name = jtable.find("caption").contents()[0].nodeValue
    return name

  get_player_name: (player) ->
    name = player.full_name
    if @is_admin_view
      name += " [#{ player.id }]"
    return name

  update_tables: (nodes) ->
    targets = $(".boxes-wrapper .ui-body")
    for node in nodes 
      comp = $(node)
      unless comp.hasClass("box-container")
        continue
      comp_id = comp.data("id")
      new_box_table = comp.find("table.boxtable")
      new_league_table = comp.find("table.leaguetable")
      new_script = comp.find("script")
      target = targets.filter (idx, elt) -> $(elt).data("id") == comp_id
      assert(target.length == 1)
      target.find("table.boxtable").replaceWith(new_box_table)
      target.find("table.leaguetable").replaceWith(new_league_table)
      target.find("script").replaceWith(new_script)

  show_results_dialog: (box) ->
    container = $("#box_results_dialog")
    container.find(".header h2").text("#{ box.name } Results")
    jqbody = container.find("table tbody")
    jqbody.children().remove()
    id_map = {}
    for e in box.entrants
      id_map[e.id] = e
      
    for match in box.matches
      if match.walkover
        continue
      unless match.points
        continue
      is_draw = false
      [p1,p2] = [0,1]
      if match.points[0] > match.points[1]
        [entrant1, entrant2] = [match.team1, match.team2]
      else if match.points[0] < match.points[1]
        [entrant2, entrant1] = [match.team1, match.team2]
        [p2,p1] = [0,1]
      else
        is_draw = true
        [entrant1, entrant2] = [match.team1, match.team2]
      [player1, player2] = (id_map[e].player1 for e in [entrant1, entrant2])
      date = wsrc.utils.iso_to_js_date(match.last_updated)
      date = wsrc.utils.js_to_readable_date_str(date)
      listify = (l) ->
        l1 = ("#{ e[p1] }&ndash;#{ e[p2] }" for e in l)
        l1.join(", ")
      tr = """
      <tr>
        <td>#{ date }</td>
        <td><span class='#{ if is_draw then '' else 'winner'}'>#{ player1.full_name }</span> vs. #{ player2.full_name }</td>
        <td>#{ listify(match.scores) }</td>
        <td class='points'>#{ listify([match.points]) }</td>
      </td>"""
      jqbody.append(tr)
    container.popup("open")

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

  make_player_id_filter: (id) ->
    return (idx, elt) ->
      $(elt).find("th.player").data("player_id") == id

  relocate_player: (player, table_name, index) ->
    target_table = @target_container_map[table_name]
    target = target_table.find("input").eq(index)
    if target.val() == ""
      target.val(@get_player_name(player))
      draggables = @set_source_player_ghost(player.id)
      draggables.draggable("disable")
        
  set_source_player_ghost: (id) ->
    rows = $("#source_boxes tr").filter(@make_player_id_filter(id))
    draggables = rows.find("th.player:not(.ui-draggable-dragging)")
    draggables.css("opacity", @ghost_opacity)
    return draggables
    
  revert_source_player_ghost: (id) ->
    rows = $("#source_boxes tr")
    if id
      rows = rows.filter(@make_player_id_filter(id))
    draggables = rows.find("th.player")
    draggables.css("opacity", 1.0)
    return draggables

    

################################################################################
# Controller - initialize and respond to events
################################################################################


class WSRC_boxes

  constructor: (@model, is_admin_view) ->
    @view = new WSRC_boxes_view(is_admin_view)
    view_radios = $("input[name='view_type']")
    view_radios.on "change", (evt) =>
      @handle_display_type_change(evt)
    $("#box-refresh-button").click (evt) =>
      @fetch_competition_group @get_competition_group_id()

  get_competition_group_id: () ->
    $("#source_boxes").data("id")

  fetch_competition_group: (group_id) ->
    jQuery.mobile.loading("show", 
      text: "Loading Competition"
      textVisible: true
      textonly: false
      theme: "a"
      html: ""
    )
    opts =
      url: "/boxes/data/#{ group_id }"
      type: 'GET'
      success: (data, status, jq_xhr) =>
        jQuery.mobile.loading("hide")
        nodes = $.parseHTML($.trim(data), null, true)
        @view.update_tables(nodes)
        @handle_display_type_change()
      failureCB: (xhr, status) -> 
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to fetch data for comp group '#{ group_id }'.")
        jQuery.mobile.loading("hide")
    jQuery.ajax(opts)


  get_points_totals: (this_box_config) ->
    newTotals = (entrant_id) -> {id: entrant_id, p: 0, w: 0, d: 0, l: 0, f: 0, a: 0, pts: 0}
    entrant_totals = {}
    for e in this_box_config.entrants
      entrant_totals[e.id] = newTotals(e.id)
    for r in this_box_config.matches
      for i in [1..2]
        entrant_id = r["team#{ i }"]
        totals = entrant_totals[entrant_id]
        unless totals?
          totals =  entrant_totals[entrant_id] = newTotals(entrant_id)
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
    entrant_totals = (totals for id,totals of entrant_totals)
    entrant_totals.sort((l,r) ->
      result = r.pts - l.pts
      if result == 0
        result = (r.f-r.a) - (l.f-l.a)
        if result == 0
          result = r.full_name < l.full_name
      result
    )
    return entrant_totals

  get_entrants: (comp_id) ->
    players = $("#box_table_#{comp_id} .player")
    factory = (jq) -> {
      id: jq.data("entrant_id")
      name: jq.text()
      player1: {full_name: jq.text()}
    }
    entrants = (factory($(p)) for p in players)
    return entrants
            
  show_score_entry_dialog: (competition_data, permitted_matches, selected_match) ->
    dialog = $('#score_entry_dialog')
    form = dialog.find("form.match-result-form")
    prefix = "Player"
    submit_callback = (data) =>
      dialog.popup("close")
      @fetch_competition_group @get_competition_group_id()
    form_controller = new wsrc.result_form(form, competition_data, permitted_matches, selected_match, prefix, submit_callback)
    form.data("controller", form_controller)
    dialog.popup('open')

  handle_league_changed: (selector) ->
    $.mobile.loading("show")
    link = $(selector).val()
    document.location = link

  handle_edit_clicked: (comp_id) ->
    matches = wsrc_boxes_data.matches[comp_id]
    entrants = @get_entrants(comp_id)
    possible_matches = matches.slice()
    mapping = {}
    # need to calculate the set of possible matches. First get matches already played:
    for m in matches
      p1 = m.team1
      p2 = m.team2
      if p1 > p2
        [p1, p2] = [p2, p1]
      mapping[wsrc.utils.cantor_pair(p1, p2)] = m
    last = entrants.length
    # Now fill in blank matches for the opponent pairs not already played
    for i in [0...last]
      row_start = i+1
      for j in [row_start...last]
        p1 = entrants[i].id
        p2 = entrants[j].id
        if p1 > p2
          [p1, p2] = [p2, p1]
        unless mapping[wsrc.utils.cantor_pair(p1, p2)]
          possible_matches.push
            team1: p1
            team2: p2
            scores: []
    competition =
      entrants: entrants
      id: comp_id
    @show_score_entry_dialog(competition, possible_matches)

  handle_display_type_change: (evt) ->
    view_radios = $("input[name='view_type']")
    view_type = view_radios.filter(":checked").val()
    @view.set_view_type(view_type)

  handle_results_clicked: (comp_id) ->
    entrants = @get_entrants(comp_id)
    matches = wsrc_boxes_data.matches[comp_id]
    @view.show_results_dialog({entrants: entrants, matches: matches})

  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: (player_list, source_competitiongroup, competition_groups) ->
    model = new WSRC_boxes_model(player_list, source_competitiongroup, competition_groups)
    @instance = new WSRC_boxes(model)

class WSRC_boxes_admin extends WSRC_boxes

  constructor: (model) ->
    super model, true
    me = this

    $("#target_boxes input.player").each (idx, elt) =>
      val = $(elt).val()
      if val
        id = @scrape_player_id(val)
        @view.set_source_player_ghost(id)
    # save and preview buttons
    @view.target_save_button = $("#target_boxes button[value='save']")
    @view.target_preview_button = $("#target_boxes button[value='preview']")
    @view.target_save_button.on "click", () =>
      @handle_target_save_click()
    @view.target_preview_button.on "click", () =>
      @handle_target_preview_click()
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

    # make source players draggable:
    @set_source_draggables()
    
    # Now set up the new league date selector...
    @view.target_end_date = $("#target_boxes input[name='end_date']")
    @mark_save_required(false)

    # Formatting, and mark dirty when the date changes 
    @view.target_end_date.datepicker
      dateFormat: "yy-mm-dd"
      onSelect: (dateText, inst) =>
        @mark_save_required()

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
      

    $("#target_boxes button.clear_all").button(
      icons: {primary: "ui-icon-arrowreturnthick-1-w"}
      text: false
    ).on "click", (evt) =>
      table = $(evt.target).parents("table")
      inputs = table.find("input")
      inputs.each (idx, elt) =>
        @revert_target_input($(elt))
      

  set_source_draggables: () ->
    $("#source_boxes th.player").draggable(
      opacity: 1.0 - @model.ghost_opacity
      helper:  "clone"
      revert:  "invalid"
      start:   (event, ui) => @handle_source_player_drag_start(event, ui)
      stop:    (event, ui) => @handle_source_player_drag_stop(event, ui)
    )

  auto_populate_new_box: (source_box) ->
    jtable = source_box.parents(".table-wrapper").find(".leaguetable")
    source_name = @view.get_table_name(source_box)
    other = (suffix) -> if suffix == "A" then "B" else "A"
    if source_name == "Premier"
      league_number = 0
      myself = sibling = "Premier"
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
      myself  = "League #{ league_number }#{ league_suffix }"
      sibling = "League #{ league_number }#{ other(league_suffix) }"
      child_1 = "League #{ league_number+1 }#{ league_suffix }"
      child_2 = "League #{ league_number+1 }#{ other(league_suffix) }"

    entrants = @collect_source_league_players(jtable)
    idx = 1
    while idx <= entrants.length
      entrant = entrants[idx-1]
      player = @model.member_map[entrant.player1.id]
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
      else if idx == 4 # fourth place, gets shifted accross to sibling league
        set_target(4, sibling)
      else if idx == 5 # 5th place gets demoted vertically to #1
        set_target(1, child_1)
      else if idx == 6 # 6th place gets demoted diagonally to #2
        if league_number == 0
          set_target(1, child_2)
        else
          set_target(2, child_2)
      if not done
        set_target(idx, myself) # default - move horizontally   
      ++idx
      
  collect_source_league_players: (jtable) ->
    entrants = []
    jtable.find("tbody th.player").each (idx1, elt) =>
      id = @scrape_player_id(elt.textContent)
      if id
        entrants.push
          player1:
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
              player1:
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
    @view.target_preview_button.prop('disabled', val)

  toggle_bulk_action: () ->
    disabled = @view.bulk_action_selector.val() == ''
    @view.bulk_action_go_button.prop("disabled", disabled)
        
  revert_target_input: (input) ->
    player_str = input.val()
    input.val("")
    id = @scrape_player_id(player_str)
    if id
      draggables = @view.revert_source_player_ghost(id)
      draggables.draggable("enable")
      @mark_save_required()

  send_league_start_email: (competition, callback) ->
    end_date = wsrc.utils.iso_to_js_date(competition.end_date)
    end_date = wsrc.utils.js_to_readable_date_str(end_date)
    data =
      competition_id: competition.id
      template_name: "StartOfNewLeague"
      subject: "New Legaues Ending #{ end_date }"
      from_address: "leagues@wokingsquashclub.org" 
    jqmask  = $("#maskdiv")
    jqmask.css("z-index", "1")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      successCB: (data, status, jq_xhr) =>
        jqmask.unmask()
        jqmask.css("z-index", "-1")
        if callback
          callback(data)
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        jqmask.css("z-index", "-1")
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nEmail for '#{ competition.name }' may not have been sent.")
    jqmask.mask("Sending start-of-league emails for \'#{ competition.name }\'...")
    wsrc.ajax.ajax_bare_helper("/boxes/admin/email", data, opts, "PUT")


  send_league_start_emails: (comp_group) ->
    jqmask  = $("#maskdiv")
    idx = 0
    doit = () =>
      if idx < comp_group.competitions_expanded.length
        doit1 = () =>
          competition = comp_group.competitions_expanded[idx]
          ++idx
          @send_league_start_email(competition, doit)
        if idx > 0
          pause = 2
          resume = () ->
            jqmask.unmask()
            jqmask.css("z-index", "-1")
            doit1()
          jqmask.mask("Waiting for #{ pause } seconds...")
          jqmask.css("z-index", "1")
          setTimeout(resume, pause * 1000)
        else
          doit1()
      else
        document.location = "/boxes/admin"
    doit()

  handle_league_changed: (selector) ->
    selector = $(selector)
    link = selector.val()
    if not @view.target_save_button.prop('disabled')
      if not confirm("Changing league will lose your changes.\n\nProceed?")
        id = @get_competition_group_id()
        selected = selector.find("option").filter (idx, elt) ->
          return $(elt).data("id") == id
        selector.val(selected.attr("value"))
        return undefined
    document.location = link

  handle_target_remove_button_click: (evt, ui) ->
    button = $(evt.target)
    input = button.parents("tr").find("input")
    @revert_target_input(input)

  handle_target_save_click: (evt, ui, callback) ->    
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
      successCB: (data, status, jqxhr) =>
        jqmask.unmask()
        jqmask.css("z-index", "-1")
        comp_group.id = data.id
        $("#target_boxes").data("id", comp_group.id)
        @mark_save_required(false)
        if callback
          callback()
      failureCB: (xhr, status, error) -> 
        jqmask.unmask()
        jqmask.css("z-index", "-1")
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to save data for '#{ comp_group.name }'.")
    
    jqmask.css("z-index", "1")
    jqmask.mask("Saving Group \'#{ comp_group.name }\'...")
    if comp_group.id?
      wsrc.ajax.ajax_bare_helper("/data/competitiongroup/#{ comp_group.id }?expand=1", comp_group, opts, "PUT")
    else
      wsrc.ajax.ajax_bare_helper("/data/competitiongroup/?expand=1", comp_group, opts, "POST")

  handle_target_preview_click: (evt, ui) ->
    target_group_id = $("#target_boxes").data("id")    
    window.open("/boxes/preview/#{ target_group_id }", "boxes_preview")

  handle_target_autocomplete_select: (evt, ui) ->
    player_str = ui.item.value
    player_id = @scrape_player_id(player_str)
    for league, comp_data of @collect_target_league_players(evt.target)
      player_ids = (e.player1.id for e in comp_data.entrants)
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
      id = wsrc.utils.to_int(source.data("player_id"))
      target.val(ui.draggable.text())
      draggables = @view.set_source_player_ghost(id)
      draggables.draggable("disable")
      @mark_save_required()
            
  handle_source_player_drag_start: (evt, ui) ->
    source = $(evt.target)
    id = wsrc.utils.to_int(source.data("player_id"))
    @view.set_source_player_ghost(id)

  handle_source_player_drag_stop: (evt, ui) ->
    source = $(evt.target)
    unless source.draggable("option").disabled
      id = wsrc.utils.to_int(source.data("player_id"))
      @view.revert_source_player_ghost(id)

  handle_bulk_action_clear: () ->
    draggables = @view.revert_source_player_ghost()
    draggables.draggable("enable")
    @view.clear_new_tables()
    @mark_save_required()

  handle_bulk_action_auto_populate: () ->
    for name, container of @view.source_container_map
      @auto_populate_new_box(container.find("table.leaguetable")) 
      @mark_save_required()

  handle_bulk_action_make_live: () ->
    make_live = () =>
      data =
        competition_group_id: $("#target_boxes").data("id")
        competition_type: "wsrc_boxes"
      jqmask  = $("#maskdiv")
      jqmask.css("z-index", "1")
      opts =
        csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
        successCB: (data, status, jq_xhr) =>
          jqmask.unmask()
          jqmask.css("z-index", "-1")
          @send_league_start_emails(data)
        failureCB: (xhr, status) -> 
          jqmask.unmask()
          jqmask.css("z-index", "-1")
          alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to make league live.")
      jqmask.mask("Setting new league active...")
      wsrc.ajax.ajax_bare_helper("/boxes/admin/activate", data, opts, "PUT")
        
    if @view.target_save_button.prop('disabled')
      make_live()
    else
      @handle_target_save_click(null, null, make_live)
    
      
  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: (player_map) ->
    model = new WSRC_boxes_model(player_map)
    @instance = new WSRC_boxes_admin(model)

    

window.wsrc.boxes = WSRC_boxes
admin = wsrc.utils.add_object_if_unset(window.wsrc, "admin")
admin.boxes = WSRC_boxes_admin
 
