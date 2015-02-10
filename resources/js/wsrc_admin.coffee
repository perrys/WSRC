
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
    jQuery.ajax(
      url: url
      type: method
      contentType: "application/json"
      data: JSON.stringify(data)
      dataType: "json"
      processData: false
      headers: headers
      success: opts.successCB
      error: opts.failureCB
      complete: (xhr, status) ->
        if opts.loadMaskId?
          jQuery("##{ opts.loadMaskId }").unmask()
    )
    return null

  find_entrant_by_id: (player_id) ->
    children = this.jq_entrant_list[0].children
    for child in children
      attr = child.attributes.getNamedItem("data-playerid")
      id = attr?.value
      if `id == player_id`
        return child
    return null
    
  entrant_already_present: (player) ->
    return this.find_entrant_by_id(player.id) != null

  find_player: (name) ->
    for id,p of this.players
      if name == p.full_name
        return p
    return null
    
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

  check_seed: (cmp) ->
    cmp = $(cmp)
    item = cmp.parent("li")
    if cmp.prop('checked')
      item.addClass("seeded")
    else
      item.removeClass("seeded")
    this.sort_seeds()
    return null

  sort_seeds: (cb) ->
    items = []
    list = this.jq_entrant_list
    list.find("li").each((idx, elt) ->
      elt.setAttribute("data-idx", idx)
      items.push(elt)
    )
    items.sort((lhs,rhs) ->
      lhs = $(lhs)
      rhs = $(rhs)
      result = rhs.hasClass('seeded') - lhs.hasClass('seeded')
      if result == 0
        result = lhs.data("idx") - rhs.data("idx")
      return result
    )
    if cb
      cb(items)
    list.empty()
    list.append(items)
    return null

  shuffle_non_seeds: () ->
    cb = (items) =>
      seeds = items.filter (elt) ->
        $(elt).hasClass('seeded')
      this.shuffle(items, seeds.length)
    this.sort_seeds(cb)
    return null

  remove_entrant: (id) ->
    entrant = this.find_entrant_by_id(id)
    if entrant
      entrant.parentElement.removeChild(entrant)
      return true
    return false

  add_entrant_item: (entrant) ->
    checked = cls = ""
    if entrant.seeded
      checked = "checked='checked'"
      cls = "seeded"
    player = entrant.player
    item = $("<li data-playerid='#{ player.id }' class='#{ cls }'>
      <input type='checkbox' onclick='WSRC_admin.check_seed(this);' #{ checked }>#{ player.full_name }
      <a class='ui-icon ui-icon-close' href='javascript:WSRC_admin.remove_entrant(#{ player.id });'></a>
      </li>"
    )
    this.jq_entrant_list.append(item)

            
  add_entrant: (form) ->
    input = $(form).find("input") 
    name = input.val()
    player = this.find_player(name)
    if player
      unless this.entrant_already_present(player)
        this.add_entrant_item
          player: player
        input.val("")
      return true

  submit_entrants: (form) ->
    form = $(form)
    entrants = []
    comp_id = competition_data.id
    this.jq_entrant_list.find("li").each (idx, elt) =>
      elt = $(elt)
      player_id = elt.data("playerid")
      entrants.push
        competition: comp_id
        handicap: null
        hcap_suffix: ""
        ordering: idx+1
        player: this.players[player_id]
        seeded: elt.hasClass("seeded")
    competition_data.entrants = entrants
    opts =
      csrf_token: form.find("input[name='csrfmiddlewaretoken']").val()
      loadMaskId: "manage_tournament"
    this.ajax_helper("/data/competition/tournament/#{ comp_id }", competition_data, opts, "PUT")
      
  onReady: (players, comp_data) ->

    this.players = players
    player_list = (obj for id,obj of players)
  
    $( "#tabs" )
      .tabs()
      .removeClass("initiallyHidden")
    $("#add_member_textbox").autocomplete(
      source: (request, response) =>
        matcher = new RegExp($.ui.autocomplete.escapeRegex(request.term), "i")
        matched_players = $.grep(player_list, (value) ->
          return matcher.test(value.full_name)
        )
        response(m.full_name for m in matched_players)
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

    entrants = comp_data?.entrants
    if entrants
      entrants.sort (lhs, rhs) ->
        lhs.ordering - rhs.ordering
      for p in entrants
        this.add_entrant_item(p)
      
    return null
