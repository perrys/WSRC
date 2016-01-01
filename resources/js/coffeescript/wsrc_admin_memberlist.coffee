
################################################################################
# Model - contains a local copy of the member databases
################################################################################

class WSRC_admin_memberlist_model
   
  constructor: (@db_memberlist, @ss_memberlist, @ss_vs_db_diffs) ->
    
    ss_valid_filter = (row) ->
      return true if row.index? or WSRC_admin_memberlist_model.convert_category_to_membership_type(row.category)
    @ss_memberlist = (row for row in @ss_memberlist when ss_valid_filter(row))

    @ss_memberlist.sort (lhs, rhs) ->
      cmp = wsrc.utils.lexical_sorter(lhs, rhs, (x) -> x.surname)
      if cmp == 0
        cmp = wsrc.utils.lexical_sorter(lhs, rhs, (x) -> x.firstname)
      return cmp

    @db_member_map = wsrc.utils.list_to_map(@db_memberlist, 'id')

  set_bs_memberlist: (list, diffs) ->
    bs_valid_filter = (row) ->
      return true if row.Name and row.Rights == "User"
    @bs_memberlist = (row for row in list when bs_valid_filter(row))
    @bs_vs_db_diffs = diffs
    
  @get_membership_type_display_name: (mem_type) ->
    # get a display name for the spreadsheet category
    tuple = wsrc.utils.list_lookup(window.wsrc_admin_memberlist_membership_types, mem_type, 0)
    return if tuple then tuple[1] else null

  @convert_category_to_membership_type: (cat) ->
    # get a (db_val, display_str) membership_type tuple for the spreadsheet category
    cvt = (x) -> if x then x.toLowerCase().replace("_", "-").replace(" ", "-") else null
    mem_type = cvt(cat)
    tuple = wsrc.utils.list_lookup(window.wsrc_admin_memberlist_membership_types, mem_type, 1, cvt)
#    console.log("#{ cat }, #{ mem_type }, #{ tuple }")
    return if tuple then tuple[0] else null

  @get_null_boolean_value: (val) ->
    unless val and val != ''
      return null
    first = val[0].toLowerCase()
    choices =
      y: true
      t: true
      n: false
      f: false
    return choices[first] or null
    
  get_missing_rows_vs_db: (other_list) ->
    other_missing = []
    db_map = {}
    for k,v of @db_member_map
      db_map[k] = v
    for other_row in other_list
      id = other_row.db_id
      if id
        delete db_map[id]
      else
        other_missing.push(other_row)
    db_missing = (item for id, item of db_map)
    wsrc.utils.lexical_sort(db_missing, "ordered_name")
    return [other_missing, db_missing]

  get_ss_vs_db_missing_rows: () ->
    return @get_missing_rows_vs_db(@ss_memberlist)

  get_bs_vs_db_missing_rows: () ->
    return @get_missing_rows_vs_db(@bs_memberlist)
                        
################################################################################
# View - JQuery interactions with the html
################################################################################

class WSRC_admin_memberlist_view
  
  constructor: (@callbacks) ->
    $("#tabs")
      .tabs()
      .removeClass("initiallyHidden")
    @db_member_table = $("#db_memberlist table.memberlist")
    @ss_member_table = $("#ss_memberlist table.memberlist")
    @bs_member_table = $("#bs_memberlist table.memberlist")

    @db_membership_colspec = [
      ['text',   'Active', 'user.is_active', 'yes_or_no[row.user.is_active]']
      ['text',   'Last Name', 'user.last_name']
      ['text',   'First Name', 'user.first_name']
      ['text',   'Category', 'membership_type', 'WSRC_admin_memberlist_model.get_membership_type_display_name(row.membership_type)']
      ['text',   'EMail', 'user.email']
      ['text',   'Receive?', 'prefs_receive_email', 'yes_or_no[row.prefs_receive_email]']
      ['number', 'WSRC ID', 'wsrc_id']
      ['number', 'CardNumber', 'cardnumber']
      ['number', 'SquashLevels ID', 'squashlevels_id']
      ['number', 'Mobile', 'cell_phone']
      ['number', 'Other Phone', 'other_phone']
    ]
    @ss_membership_colspec = [
      ['text',   'Active', 'active']
      ['text',   'Surname', 'surname']
      ['text',   'First Name', 'firstname']
      ['text',   'Category', 'category']
      ['text',   'EMail', 'email']
      ['text',   'Receive?', 'Data Prot email', 'row["Data Prot email"]']
      ['number', 'WSRC ID', 'index']
      ['number', 'Cardnumber', 'cardnumber']
      ['number', 'Mobile', 'mobile_phone']
      ['number', 'Home Phone', 'home_phone']
    ]
    @bs_membership_colspec = [
      ['text',   'Last Name', 'last_name']
      ['text',   'First Name', 'first_name']
      ['text',   'EMail', 'Email address', 'row["Email address"]']
      ['number', 'Mobile', 'Mobile']
      ['number', 'Telephone', 'Telephone']
    ]

  get_display_col: (db_field) ->
    cls = field = ''
    for spec in @db_membership_colspec
      if db_field == spec[2]
        cls = spec[0]
        field = spec[1]
        break
    return [cls, field]

  get_comparison_table: (tab_id, table_class) ->
    return $("##{ tab_id } table.#{ table_class }")
  
  add_to_table: (table, col_spec, row) ->
    table_body = table.find("tbody")
    yes_or_no =
      true: 'yes'
      false: 'no'
      null: ''
    data_id = ""
    if row.id
      data_id = "data-id='#{ row.id }'"
    table_row = "<tr #{ data_id }>"
    for spec in col_spec
      table_row += "<td class='#{ spec[0] } #{ spec[2].replace(".", "_").replace(" ", "_") }' data-col='#{ spec[2] }'>"
      val = if spec.length > 3 then eval(spec[3]) else eval("row.#{ spec[2] }")
      val = val ? ""
      table_row += val + "</td>"
    table_row += "</tr>"
    table_row = $(table_row)
    table_body.append(table_row)
    return table_row
          
  add_db_member: (member) ->
    table_row = @add_to_table(@db_member_table, @db_membership_colspec, member)

  add_ss_member: (member) ->
    table_row = @add_to_table(@ss_member_table, @ss_membership_colspec, member)

  add_bs_member: (member) ->
    table_row = @add_to_table(@bs_member_table, @bs_membership_colspec, member)

  populate_differences_tab: (tab_id, colspec, missing_from_db_list, missing_from_other_list, differences, add_button_callback) ->
    for jq in [$("##{ tab_id }"), $("li[aria-controls='#{ tab_id }']")]
      jq.removeClass('ui-helper-hidden')
    missing_from_db_table    = @get_comparison_table(tab_id, "missing_from_db")
    missing_from_other_table = @get_comparison_table(tab_id, "missing_from_other")
    differences_table        = @get_comparison_table(tab_id, "differences")
    
    for member in missing_from_db_list
      table_row = @add_to_table(missing_from_db_table, colspec, member)
      if add_button_callback
        add_button_callback(table_row)
    for member in missing_from_other_list
      @add_to_table(missing_from_other_table, @db_membership_colspec, member)

    wsrc.utils.apply_alt_class(missing_from_db_table.find("tbody").children(), "alt")
    wsrc.utils.apply_alt_class(missing_from_other_table.find("tbody").children(), "alt")
    missing_from_other_table.find("tbody").children().dblclick(@callbacks.id_row_open_admin_click_handler)
    
    diff_cols = {}
    for id, row of differences
      for field, diff of row
        diff_cols[field] = field
    diff_cols = (c[2] for c in @db_membership_colspec when c[2] of diff_cols) # order cols consistently with main table
    diff_cols = ([c, @get_display_col(c)[0], @get_display_col(c)[1]] for c in diff_cols)

    add_col = (cls, field) ->
      header = $("<th class='#{ cls }'>#{ field }</th>")
      differences_table.find("thead tr").append(header)
      return header

    add_row = (id, row) ->
      new_row = ""
      for val in row
        if val
          [cls, field, val] = val
          new_row += "<td class='#{ cls }' data-field='#{ field }'>#{ val }</td>"
        else
          new_row += "<td></td>"
      differences_table.find("tbody").append("<tr data-id='#{ id }'>#{ new_row }</tr>")
                      
    header = add_col("sortable", "Record")
    header.attr("data-selector", "td.id_field")
    header.attr("data-sorter", "lexical_sorter")
    header.data("reverse", false)
    for [field, cls, display] in diff_cols
      add_col('', display)

    for id,row of differences
      unless row
        continue
      db_record = @callbacks.lookup_db_member(id)
      row_vals = [["text id_field", null, "<div>#{ db_record.user.last_name }, #{ db_record.user.first_name }</div>"]]
      for [field, cls] in diff_cols
        diff = row[field]
        if diff          
          row_vals.push(["#{ cls } diff_field", field, "<div class='from'>#{ row[field][1] }</div><div class='to'>#{ row[field][0] }</div>"])
        else
          row_vals.push(null)
      add_row(id, row_vals)

    handler = wsrc.utils.configure_sortable(differences_table.find("thead th.sortable"))
    handler()
    differences_table.find("td.diff_field").on('contextmenu', @callbacks.open_change_details_handler)    
    differences_table.find("tbody").children().dblclick(@callbacks.id_row_open_admin_click_handler)
            
  show_change_member_details_form: (field, new_val, submit_path, id, row_id, source_div_id) ->
    jqdialog = $("#change_member_form_dialog")
    jqform = jqdialog.find("form")
    jqform.find("div.ui-field-contain").hide()
    jqform.data("field", field)
    jqform.data("path", submit_path)
    jqform.data("id", id)
    jqform.data("row_id", row_id)
    jqform.data("source_div_id", source_div_id)
    
    jqinput = jqform.find("[name='#{ field }']")
    jqinput.val(new_val)
    jqinput.parents("div.ui-field-contain").show()
    jqdialog.dialog(
      width: 450
      height: 175
      autoOpen: false
      model: true
      dialogClass: "new_member_form_dialog"
    )
    jqdialog.dialog("open")
    
  hide_change_member_form: () ->
    jqdialog = $("#change_member_form_dialog")
    jqdialog.dialog("close")

  get_changed_member_details : () ->
    jqdialog = $("#change_member_form_dialog")
    jqform  = jqdialog.find("form")
    field   = jqform.data("field")
    path    = jqform.data("path")
    id      = jqform.data("id")
    row_id  = jqform.data("row_id")
    source  = jqform.data("source_div_id")
    jqinput = jqform.find("[name='#{ field }']")
    val = jqinput.val()
    return [field, val, path, id, row_id, source]
    
  show_new_member_form: (user_obj, player_obj) ->
    jqdialog = $("#new_member_form_dialog")
    for key, val of user_obj
      jqdialog.find("fieldset.user [name='#{ key }']").val("#{ val }")
    for key, val of player_obj
      jqdialog.find("fieldset.player [name='#{ key }']").val("#{ val }")
    jqdialog.dialog(
      width: 450
      height: 550
      autoOpen: false
      model: true
      dialogClass: "new_member_form_dialog"
    )
    jqdialog.dialog("open")

  hide_new_member_form: () ->
    jqdialog = $("#new_member_form_dialog")
    jqdialog.dialog("close")

  get_booking_system_credentials: () ->
    jqform = $("form#booking_system_credentials")
    credentials =
      username: jqform.find("[name='username']").val()
      password: jqform.find("[name='password']").val()

  hide_booking_system_credentials_form: () ->
    $("form#booking_system_credentials").hide()

  get_new_member_details: () ->
    jqdialog = $("#new_member_form_dialog")
    user_obj =
      username:     null
      password:     null
      is_active:    null
      last_name:    null
      first_name:   null
      email:        null
    player_obj = 
      membership_type:     null
      prefs_receive_email: null
      wsrc_id:             null
      cardnumber:          null
      cell_phone:          ''
      other_phone:         ''
    for key,val of user_obj
      user_obj[key] = jqdialog.find("fieldset.user [name='#{ key }']").val() or null
    for key,val of player_obj
      val = jqdialog.find("fieldset.player [name='#{ key }']").val()
      if val
        player_obj[key] = val
    return [user_obj, player_obj]  
    

################################################################################
# Controller - initialize and respond to events
################################################################################

class WSRC_admin_memberlist 

  constructor: (@model) ->
    
    callbacks = 
      id_row_open_admin_click_handler: (evt) =>
        @id_row_open_admin_click_handler(evt)
      open_change_details_handler: (evt) =>
        evt.preventDefault();
        @open_change_details_handler(evt)
        return false;
      lookup_db_member: (id) => @model.db_member_map[id]

    @view = new WSRC_admin_memberlist_view(callbacks)
    
    for member in @model.db_memberlist
      @view.add_db_member(member)
    for member in @model.ss_memberlist
      @view.add_ss_member(member)
      
    wsrc.utils.apply_alt_class(@view.ss_member_table.find("tbody").children(), "alt")
    wsrc.utils.apply_alt_class(@view.db_member_table.find("tbody").children(), "alt")
    
    [missing_from_db, missing_from_ss] = model.get_ss_vs_db_missing_rows()
    missing_from_db = (x for x in missing_from_db when x.active?.toLowerCase()[0] == 'y')
    missing_from_ss = (x for x in missing_from_ss when x.user.is_active)

    add_button_callback = (table_row) ->
      table_row.append("<td><button onclick='wsrc.admin.memberlist.on(\"show_new_member_form\", this)'>Add</button></td>")
      id = table_row.find("td.index").text()
      if id
        table_row.attr("id", "added_member_#{ id }")

    @view.populate_differences_tab("ss_vs_db_diffs", @view.ss_membership_colspec, missing_from_db, missing_from_ss, @model.ss_vs_db_diffs, add_button_callback)

    wsrc.utils.configure_sortables()

    $("form#booking_system_credentials").on("submit", () => @booking_system_fetch_memberlist_handler())
    @view.db_member_table.find("tbody td").dblclick(callbacks.id_row_open_admin_click_handler)
        
  booking_system_update_tables: (data) ->
    @model.set_bs_memberlist(data.contacts, data.diffs)
    
    for member in @model.bs_memberlist
      @view.add_bs_member(member)
      
    wsrc.utils.apply_alt_class(@view.bs_member_table.find("tbody").children(), "alt")
    
    [missing_from_db, missing_from_bs] = @model.get_bs_vs_db_missing_rows()
    missing_from_bs = (x for x in missing_from_bs when x.user.is_active)
    
    @view.populate_differences_tab("bs_vs_db_diffs", @view.bs_membership_colspec, missing_from_db, missing_from_bs, @model.bs_vs_db_diffs)
    wsrc.utils.configure_sortables()


  show_new_member_form: (elt) ->

    row = $(elt).parents("tr")
    data_vals = {}
    row.children().each (idx, elt) =>
      elt = $(elt)
      data_vals[elt.data("col")] = elt.text()
    user_obj =
      is_active:    data_vals["active"][0]?.toLowerCase() == "y"
      last_name:    data_vals["surname"]
      first_name:   data_vals["firstname"]
      email:        data_vals["email"]
    player_obj = 
      membership_type:     WSRC_admin_memberlist_model.convert_category_to_membership_type(data_vals["category"])
      prefs_receive_email: WSRC_admin_memberlist_model.get_null_boolean_value(data_vals["Data Prot email"])
      wsrc_id:             wsrc.utils.to_int(data_vals["index"])
      cardnumber:          data_vals["cardnumber"]
      cell_phone:          data_vals["mobile_phone"]
      other_phone:         data_vals["home_phone"]
    user_obj.username = "#{ user_obj.first_name }_#{ user_obj.last_name }".toLowerCase().replace(" ", "_")
    user_obj.password = "squash#{ if player_obj.cardnumber then player_obj.cardnumber.slice(-3) else '123' }"
    @view.show_new_member_form(user_obj, player_obj, elt)

  new_member_submit_handler: () ->
    [user_obj, player_obj] = @view.get_new_member_details()
    csrf_token = $("input[name='csrfmiddlewaretoken']").val()
    jqmask = $("body")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      successCB: (data, status, jq_xhr) =>
        jqmask.unmask()
        @view.hide_new_member_form()
        jrow = $("tr#added_member_#{ player_obj.wsrc_id }")
        jtbody = jrow.parent()
        jrow.remove()        
        wsrc.utils.apply_alt_class(jtbody.children(), "alt")
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to add new user.")
    player_obj.user = user_obj
    jqmask.mask("Creating new user...")
    wsrc.ajax.ajax_bare_helper("/data/memberlist/player/", player_obj, opts, "POST")

  open_user_admin_page: (id) ->
    player = @model.db_member_map[id]
    if player
      url = "/admin/auth/user/#{ player.user.id }/"
      window.open(url, "_blank")
    
  id_row_open_admin_click_handler: (evt) ->
    id = $(evt.target).parents("tr").data("id")
    @open_user_admin_page(id)

  open_change_details_handler: (evt) ->
    jtarget = $(evt.target)
    jcell   = jtarget.parents("td")
    jrow    = jtarget.parents("tr")
    id      = wsrc.utils.to_int(jrow.data("id"))
    field   = jcell.data("field")
    from    = jcell.find("div.from").text()
    to      = jcell.find("div.to").text()
    source  = jcell.parents("div.comparison_wrapper").attr("id")
    if field.startsWith("user.")
      player = @model.db_member_map[id]
      obj_id = player.user.id
      path = "/data/memberlist/user/#{ id }"
      field = field.replace("user.", "") 
    else
      path = "/data/memberlist/player/#{ id }"
      obj_id = id
    @view.show_change_member_details_form(field, to, path, obj_id, id, source)

  change_member_submit_handler: () ->
    [field, val, path, id, row_id, source_div_id] = @view.get_changed_member_details()
    data = {id: id}
    data[field] = val
    jtable = @view.get_comparison_table(source_div_id, "differences")
    jrow = jtable.find("tbody tr").filter (idx, elt) -> $(elt).data("id") == row_id
    jcell = jrow.find("td").filter (idx, elt) -> $(elt).data("field") == field
    jqmask  = $("body")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      successCB: (data, status, jq_xhr) =>
        @view.hide_change_member_form()
        jqmask.unmask()
        jcell.children().remove()
        jcell.off('contextmenu')
        if 0 == jrow.find("div.to").length
          jrow.remove()
          wsrc.utils.apply_alt_class(jtable.find("tbody").children(), "alt")
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to update user.")
    jqmask.mask("Updating user details...")
    wsrc.ajax.ajax_bare_helper(path, data, opts, "PATCH")

  booking_system_fetch_memberlist_handler: () ->
    data = @view.get_booking_system_credentials()
    jqmask  = $("body")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      successCB: (data, status, jq_xhr) =>
        jqmask.unmask()
#        @view.hide_booking_system_credentials_form()
        @booking_system_update_tables(data)
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to fetch member list.")
    jqmask.mask("Fetching contact details from booking system...")
    wsrc.ajax.ajax_bare_helper("/data/memberlist/bookingsystem/", data, opts, "POST");
    return false

  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: (db_memberlist, ss_memberlist, ss_vs_db_diffs) ->
    model = new WSRC_admin_memberlist_model(db_memberlist, ss_memberlist, ss_vs_db_diffs)
    @instance = new WSRC_admin_memberlist(model)


admin = wsrc.utils.add_object_if_unset(window.wsrc, "admin")
admin.memberlist = WSRC_admin_memberlist

              
