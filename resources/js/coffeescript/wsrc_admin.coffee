
window.WSRC_admin =

  players: null
  jq_entrant_list: null

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
    if opts.loadMaskId?
      msg = if method == "GET" then "Loading..." else "Saving..."
      jQuery("##{ opts.loadMaskId }").mask(msg)
    headers = {}
    if opts.csrf_token?
      headers["X-CSRFToken"] = opts.csrf_token
    settings =
      url: url
      type: method
      contentType: "application/json"
      data: JSON.stringify(data)
      headers: headers
      success: opts.successCB
      error: opts.failureCB
      complete: (xhr, status) ->
        if opts.loadMaskId?
          jQuery("##{ opts.loadMaskId }").unmask()
    if method == "GET"
      settings.dataType = "json" # expected return value
    else
      settings.processData = false
    jQuery.ajax(settings)
    return null

  find_entrant_by_id: (player_id) ->
    children = this.jq_entrant_list[0].children
    for child in children
      child = $(child)
      for attr in ["playerid", "player2id"]        
        id = child.data(attr)
        if `id == player_id`
          return child
    return null
    
  entrant_already_present: (player) ->
    return this.find_entrant_by_id(player.id) != null

  shuffle: (array, offset) ->
    # Fisher-Yates shuffle, with offset
    m = array.length - offset    
    while (m) # While there remain elements to shuffle
      # Pick a remaining element
      i = Math.floor(Math.random() * m--)
      # And swap it with the current element
      rhs = m + offset
      lhs = i + offset      
      t = array[rhs];
      array[rhs] = array[lhs];
      array[lhs] = t;
    return array;

  sort_seeds: (cb) ->
    sorter = (lhs, rhs) -> rhs.hasClass('seeded') - lhs.hasClass('seeded')
    jq_list = @jq_entrant_list.find("li")
    items = wsrc.utils.jq_stable_sort(jq_list, sorter)
    if cb
      cb(items)
    @jq_entrant_list.empty()
    @jq_entrant_list.append(items)
    return null

  sort_handicap: (cb) ->
    items = []
    list = this.jq_entrant_list
    list.find("li").each((idx, elt) ->
      elt.setAttribute("data-idx", idx)
      items.push(elt)
    )
    get_hcap = (elt) ->
      parseInt(elt.find("input.handicap").val())
    items.sort((lhs,rhs) ->
      lhs = $(lhs)
      rhs = $(rhs)
      result = get_hcap(lhs) - get_hcap(rhs)
      if result == 0
        result = lhs.data("idx") - rhs.data("idx")
      return result
    )
    list.empty()
    list.append(items)
    return null

  get_comp_type: () ->
    $("input[name='tournament_type']:checked").val()

      
  add_entrant_item: (entrant) ->
    comp_type = this.get_comp_type()
    seed_class = if comp_type in ["seeded", "doubles"] then "" else "hidden"
    hcap_class = if comp_type == "handicap" then "" else "hidden"
    player2_class = if comp_type == "doubles" then "" else "hidden"
    hcap_val = if entrant.handicap != null then entrant.handicap else ""
    checked = cls = ""
    unless entrant.player2
      entrant.player2 =
        id: ''
        full_name: ''
    if entrant.seeded
      checked = "checked='checked'"
      cls += " seeded"
    if comp_type == "doubles"
      cls += " doubles"
    item = $("<li data-playerid='#{ entrant.player.id }' data-player2id='#{ entrant.player2.id }' class='#{ cls }'>
      <input type='checkbox' class='seeded #{ seed_class }' onclick='WSRC_admin.on_toggle_seed(this);' #{ checked }>
      <input type='number' class='handicap #{ hcap_class }' min='-100' max='15' size='2' value='#{ hcap_val }'>
      <div class='player1'>
        #{ entrant.player.full_name }
      </div>
      <input class='player2 doubles #{ player2_class }' value='#{ entrant.player2.full_name }'>
      <a class='ui-icon ui-icon-close' href='#' onclick='WSRC_admin.on_remove_entrant(#{ entrant.player.id });'></a>
      </li>"
    )
    this.jq_entrant_list.append(item)
    p2_input = item.find("input.player2")
    p2_input.autocomplete(
      source: this.player_list
      select: (evt, ui) =>
        id = WSRC_admin.on_auto_complete(p2_input, evt, ui)
        player = this.players[id]
        entrant = this.find_entrant_by_id(id)
        if entrant != null
          alert("WARNING: Player #{ player.full_name } [#{ id }] is already an entrant")
        p2_input.parent('li').data("player2id", id)
    )

  on_comp_type_toggled: () ->
    comp_type = this.get_comp_type()
    this.jq_entrant_list.find("input").addClass("hidden")
    this.jq_entrant_list.find("input.#{ comp_type }").removeClass("hidden")
    items = this.jq_entrant_list.find("li")
    if comp_type == "doubles"
      items.addClass("doubles")
      this.jq_entrant_list.find("input.seeded").removeClass("hidden")
    else
      items.removeClass("doubles")    

  on_shuffle_non_seeds: () ->
    cb = (items) =>
      seeds = items.filter (elt) ->
        $(elt).hasClass('seeded')
      this.shuffle(items, seeds.length)
    this.sort_seeds(cb)
    return null

  on_add_round: (date) ->
    button = $("#add_round_button")
    if not date
      date = ""
    elt = $("<div class='round-date'>
      <input name='round' class='round-date' value='#{ date }'>
      <a class='ui-icon ui-icon-close' href='#' onclick='WSRC_admin.on_remove_round(this);'></a>
      </div>
    ")
    button.before(elt)
    elt.find("input").datepicker
      dateFormat: "yy-mm-dd"
    
  on_remove_round: (elt) ->
    $(elt).parent("div").remove()
    
  on_toggle_seed: (cmp) ->
    cmp = $(cmp)
    item = cmp.parent("li")
    if cmp.prop('checked')
      item.addClass("seeded")
    else
      item.removeClass("seeded")
    this.sort_seeds()
    return null

  on_auto_complete: (cmp, event, ui) ->
    event.preventDefault()
    cmp.val(ui.item.label)
    player_id = parseInt(ui.item.value)
    player = this.players[player_id]
    unless player
      alert("Unable to find player #{ ui.item.label } [#{ ui.item.value }]")
    cmp.data('playerid', player_id)
    return player_id

  on_add_entrant: (form) ->
    input = $(form).find("input") 
    name = input.val()
    tokens = name.split("/")
    hcap = null
    if tokens.length > 1
      name = tokens[0]
      hcap_val = tokens[1]
    player_id = parseInt(input.data("playerid"))
    player = this.players[player_id]
    if player
      unless this.entrant_already_present(player)
        this.add_entrant_item
          player: player
          handicap: hcap_val
        input.val("")
      return true

  on_remove_entrant: (id) ->
    entrant = this.find_entrant_by_id(id)
    if entrant
      entrant.remove()
      return true
    return false

  on_submit_entrants: (form) ->
    form = $(form)
    entrants = []
    comp_id = competition_data.id
    comp_type = this.get_comp_type()
    this.jq_entrant_list.find("li").each (idx, elt) =>
      elt = $(elt)
      player_id = elt.data("playerid")
      handicap = if comp_type == "handicap" then elt.find("input.handicap").val() else null
      player2_id = if comp_type == "doubles" then elt.data("player2id") else null
      entrants.push
        competition: comp_id
        handicap: handicap
        hcap_suffix: ""
        ordering: idx+1
        player:  this.players[player_id]
        player2: this.players[player2_id]
        seeded: elt.hasClass("seeded")
    competition_data.entrants = entrants
    dates = []
    $("div.round-date input").each (idx, elt) ->
      dates.push($(elt).val())
    dates.sort()
    competition_data.rounds = ({round: num, end_date: dates[num-1]} for num in [1..dates.length])
    opts =
      csrf_token: form.find("input[name='csrfmiddlewaretoken']").val()
      loadMaskId: "manage_tournament"
      failureCB: (xhr, status) => 
          alert("ERROR: Failed to save, status: #{ status }")
        
    this.ajax_helper("/data/competition/tournament/#{ comp_id }", competition_data, opts, "PUT")
      
  onReady: (players, comp_data) ->

    this.players = players
    this.player_list = ({label: p.full_name, value: id} for id,p of players)
    $( "#tabs" )
      .tabs()
      .removeClass("initiallyHidden")
    add_member_input = $("#add_member_textbox")
    add_member_input.autocomplete(
      source: this.player_list
      select: (evt, ui) ->
        WSRC_admin.on_auto_complete(add_member_input, evt, ui)
    )

    $("input").addClass("ui-corner-all")
    $("select").addClass("ui-corner-all")

    $("input[name='end_date']").each (index, elt) ->
        $(elt).datepicker(
          dateFormat: "yy-mm-dd"
        )

    this.jq_entrant_list = $("ol.entrants_list")
    this.jq_entrant_list
      .sortable(
        placeholder: "ui-state-highlight"
      )
      .on("sortupdate", (evt, ui) =>
        this.sort_seeds()
      )
      .disableSelection()

    if comp_data?.name
      comp_type = if comp_data.name.indexOf("Handicap") < 0 then "seeded" else "handicap"
      if comp_data.name.indexOf("Doubles") >= 0
        comp_type = "doubles"
      radios = $("input[name='tournament_type']")
      radios.filter("[value='#{ comp_type }']").prop("checked", true)
              
      entrants = comp_data?.entrants
      if entrants
        entrants.sort (lhs, rhs) ->
          lhs.ordering - rhs.ordering
        for p in entrants
          this.add_entrant_item(p)

      rounds = comp_data?.rounds
      if rounds
        rounds.sort (lhs,rhs) ->
          lhs.end_date - rhs.end_date
        for r in rounds
          this.on_add_round(r.end_date)
      
    return null
