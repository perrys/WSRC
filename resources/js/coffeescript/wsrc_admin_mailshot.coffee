
class WSRC_admin_mailshot 

  individual_ids: []

  constructor: (@player_map) ->
    player_list = ({label: p.full_name, value: id} for id,p of @player_map)
    wsrc.utils.lexical_sort(player_list, 'label')
    $("input[name='respect_opt_out']").on("change", (evt) => @selected_players_changed(evt))
    $("input[name='member_type']").on("change", (evt) => @selected_players_changed(evt))
    add_member_input = $("input#add_member")
    add_member_input.autocomplete(
      source: player_list
      select: (evt, ui) =>
        @member_selected(add_member_input, evt, ui)
    )
    jqdialog = $("#selected_member_table")
    jqdialog.dialog(
      width: 700
      height: 400
      autoOpen: false
      model: true
      dialogClass: "selected_member_dialog"
    )
    @selected_players_changed()

  show_selected_members_table: () ->
    players = @get_selected_players()
    jqdialog = $("#selected_member_table")
    jqtbody = jqdialog.find("table tbody")
    jqtbody.find("tr:not(.header-row)").remove()
    wsrc.utils.lexical_sort(players, "full_name")
    for p in players
      optout = if p.prefs_receive_email == "False" then "Yes" else ""
      jqtbody.append("<tr><td>#{ p.full_name }</td><td>#{ p.email }</td><td>#{ p.membership_type }</td><td>#{ optout }</td></tr>")
    jqdialog.dialog("open")
        
  add_individual: (form) ->
    add_member_input = $(form).find("input#add_member")
    id = add_member_input.data("playerid")
    @individual_ids.push(id)
    add_member_input.val('')
    @selected_players_changed()

  clear_individuals: (form) ->
    @individual_ids = []
    @selected_players_changed()
    
  get_selected_players: () ->
    selection_type = $('select#recipient_selector').val()
    if selection_type == 'individuals'
      return (@player_map[id] for id in @individual_ids)
    else
      all_players = (p for id,p of @player_map)
      if selection_type == 'all'
        return all_players
      else if selection_type == 'member_type'
        member_types = {}
        jqmember_types = $("div#member_type").find("input[name='member_type']:checked")
        # build a set of selected member types using $.each:
        jqmember_types.each (idx, elt) ->
          member_types[elt.value] = true
        # filter down to selected member types using $.grep:
        filtered_players = $.grep all_players, (player, idx) ->
          if member_types[player.membership_type] then true else false
        return filtered_players
    
  member_selected: (cmp, event, ui) ->
    event.preventDefault()
    cmp.val(ui.item.label)
    player_id = parseInt(ui.item.value)
    player = this.player_map[player_id]
    unless player
      alert("Unable to find player #{ ui.item.label } [#{ ui.item.value }]")
    cmp.data('playerid', player_id)
    return player_id

  selected_players_changed: () ->
    selected_players = @get_selected_players()
    respect_opt_outs = $("input[name='respect_opt_out']:checked").val() == "true"
    results = WSRC_admin_mailshot.count_players(selected_players, respect_opt_outs)
    nplayers = results.distinct_players.length
    nemails = results.distinct_emails.length
    jqspan = $("span#totals")
    jqspan.html("""
      #{ nplayers } member#{ wsrc.utils.plural(nplayers) },
      #{ results.num_to_receive_email } to receive email,
      #{ nemails } distinct email address#{ wsrc.utils.plural(nemails, 'es') }
      <a href='javascript:wsrc.admin.mailshot.on("show_selected_members_table")' class='#{ if nplayers == 0 then "ui-helper-hidden" }'>(show)</a>
    """)
            
  recipient_selector_changed: (selector) ->
    jqselector = $(selector)
    val = jqselector.val()
    fieldset = jqselector.parents("fieldset")
    fieldset.find("div.selection-type:not(##{ val })").addClass("ui-helper-hidden")
    fieldset.find("##{ val }").removeClass("ui-helper-hidden")
    @selected_players_changed()

  @count_players: (player_list, filter_optouts) ->
    players = {}
    players_with_email = 0
    emails = {}
    for player in player_list
      if players[player.id]
        continue
      players[player.id] = player
      if filter_optouts && (player.prefs_receive_email == "False")
        continue
      if player.email.indexOf("@") > 0
        players_with_email += 1
        emails[player.email] = true
    return {
      distinct_players: (p for id,p of players)
      num_to_receive_email: players_with_email
      distinct_emails: (e for e,val of emails)
    }

  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: (players) ->
    @instance = new WSRC_admin_mailshot(players)
    
    return null
    
admin = wsrc.utils.add_object_if_unset(window.wsrc, "admin")
admin.mailshot = WSRC_admin_mailshot

