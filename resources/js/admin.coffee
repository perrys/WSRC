
window.WSRC_admin =

  players: null
  jq_entrant_list: null

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
    for p in this.players
      if name == p.name
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

  add_entrant_item: (player) ->
    checked = cls = ""
    if player.seeding
      checked = "checked='checked'"
      cls = "seeded"
    item = $("<li data-playerid='#{ player.id }' class='#{ cls }'>
      <input type='checkbox' onclick='WSRC_admin.check_seed(this);' #{ checked }>#{ player.name }
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
        this.add_entrant_item(player)
        input.val("")
      return true

  submit_entrants: (form) ->
    form = $(form)
    entrants = form.find("select[name='players']")
    seeds = []    
    this.jq_entrant_list.find("li").each (idx, elt) ->
      elt = $(elt)
      player_id = elt.data("playerid")
      entrants.append("<option value='#{ player_id }' selected='selected'> </option>")
      if elt.hasClass("seeded")
        seeds.push(player_id)
    comma_sep = (list) ->
      t = ""
      for l in list
        if t.length > 0
          t += ","
        t += l
      return t
    form.find("input[name='seeds']").val(comma_sep(seeds))
      
  onReady: (players, initial_entrants) ->

    this.players = players
    
    $( "#tabs" )
      .tabs()
      .removeClass("initiallyHidden")
    $("#add_member_textbox").autocomplete(
      source: (request, response) =>
        matcher = new RegExp($.ui.autocomplete.escapeRegex(request.term), "i")
        matched_players = $.grep(players, (value) ->
          return matcher.test(value.name)
        )
        response(m.name for m in matched_players)
    )

    $("input").addClass("ui-corner-all")
    $("select").addClass("ui-corner-all")

    $("input[name='end_date']").each (index, elt) ->
        console.log(elt)
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

    for p in initial_entrants
      this.add_entrant_item(p)
      
    return null
