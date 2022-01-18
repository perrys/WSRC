
class WSRC_admin_mailshot 

  individual_ids: []

  constructor: (@player_map, @box_player_ids, @tournament_player_ids, @squash57_box_player_ids) ->
    player_list = ({label: p.full_name, value: id} for id,p of @player_map)
    wsrc.utils.lexical_sort(player_list, 'label')
    $("input[name='respect_opt_out']").on("change", (evt) => @selected_players_changed(evt))
    $("input[name='member_type']").on("change", (evt) => @selected_players_changed(evt))
    $("input[name='comp_type']").on("change", (evt) => @selected_players_changed(evt))
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
    selected_players = @get_selected_players()
    results = WSRC_admin_mailshot.count_players(selected_players, @opt_outs_respected())
    players = results.distinct_players
    jqdialog = $("#selected_member_table")
    jqtbody = jqdialog.find("table tbody")
    jqtbody.find("tr:not(.header-row)").remove()
    wsrc.utils.lexical_sort(players, "ordered_name")
    for p in players
      email_pref = if p.prefs_receive_email == null then "unspecified" else p.prefs_receive_email
      row = $("<tr><td>#{ p.ordered_name }</td><td>#{ p.email }</td><td>#{ p.subscription_type.name }</td><td>#{ email_pref }</td></tr>")
      unless p.email in results.distinct_emails
        row.addClass("ui-state-disabled")
      jqtbody.append(row)
    jqdialog.dialog("open")

  send_email: () ->
    selected_players = @get_selected_players()
    results = WSRC_admin_mailshot.count_players(selected_players, @opt_outs_respected())
    csrf_token = $("input[name='csrfmiddlewaretoken']").val()
    email_addresses = results.distinct_emails
    jqmask = $("body")
    batch_size = 40
    data =
      subject:      $("input[name='subject']").val()
      body:         $("textarea[name='email_body']").val()
      from_address: $("select[name='from_input']").val()
      to_list:      ["members@wokingsquashclub.org"]
      format:       $("input[name='email_format']:checked").val()
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nThis batch of email failed to send.")
    iterate = (start) ->
      end = Math.min(start + batch_size, email_addresses.length)
      batch = email_addresses[start...end]
      data['bcc_list'] = batch
      opts['successCB'] = (xhr, status) ->
        jqmask.unmask()
        if end < email_addresses.length
          pause = 5
          jqmask.mask("Waiting for #{ pause } seconds...")
          resume = () ->
            jqmask.unmask()
            iterate(end)
          setTimeout(resume, pause * 1000)
      jqmask.mask("Sending emails #{ start+1 } to #{ end } of #{ email_addresses.length }...")
      wsrc.ajax.ajax_bare_helper("/admin/mailshot/send", data, opts, "PUT")
    iterate(0)
      
  add_individual: (form) ->
    add_member_input = $(form).find("input#add_member")
    id = add_member_input.data("playerid")
    if id
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
    else if selection_type == 'competition_entrants'
      ids = {}
      jqcomp_entrants = $("div#competition_entrants").find("input[name='comp_type']:checked")
      jqcomp_entrants.each (idx, elt) =>
        id_list = this["#{ elt.value }_player_ids"]
        for id in id_list
          ids[id] = true
      return (@player_map[id] for id,flag of ids)
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
          if member_types[player.subscription_type.id] then true else false
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

  opt_outs_respected: () ->
    $("input[name='respect_opt_out']:checked").val() == "true"

  selected_players_changed: () ->
    selected_players = @get_selected_players()
    results = WSRC_admin_mailshot.count_players(selected_players, @opt_outs_respected())
    nplayers = results.distinct_players.length
    nemails = results.distinct_emails.length
    jqspan = $("span#totals")
    jqspan.html("""
      <strong>#{ nplayers }</strong> member#{ wsrc.utils.plural(nplayers) },
      <strong>#{ results.num_to_receive_email }</strong> to receive email,
      <strong>#{ nemails }</strong> distinct email address#{ wsrc.utils.plural(nemails, 'es') }
      <a href='#' onclick='wsrc.admin.mailshot.on("show_selected_members_table")' class='#{ if nplayers == 0 then "ui-helper-hidden" else "" }'>(show)</a>
    """)
            
  recipient_selector_changed: (selector) ->
    jqselector = $(selector)
    val = jqselector.val()
    fieldset = jqselector.parents("fieldset")
    fieldset.find("div.selection-type:not(##{ val })").addClass("ui-helper-hidden")
    fieldset.find("##{ val }").removeClass("ui-helper-hidden")
    @selected_players_changed()

  @opted_out: (player) ->
    opted_in = player.prefs_receive_email == true or player.prefs_receive_email == "True"
    return not opted_in

  @count_players: (player_list, filter_optouts) ->
    players = {}
    players_with_email = 0
    emails = {}
    for player in player_list
      if players[player.id]
        continue
      players[player.id] = player
      if filter_optouts && @opted_out(player)
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

  @onReady: (players, box_player_ids, tournament_player_ids, squash57_box_player_ids) ->
    @instance = new WSRC_admin_mailshot(players, box_player_ids, tournament_player_ids, squash57_box_player_ids)
    
    return null
    
admin = wsrc.utils.add_object_if_unset(window.wsrc, "admin")
admin.mailshot = WSRC_admin_mailshot

