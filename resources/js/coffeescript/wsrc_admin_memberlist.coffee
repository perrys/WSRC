
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

    @db_member_map = {}
    reducer = (result, item) ->
      result[item.id] = item
      return result
    @db_memberlist.reduce(reducer, @db_member_map)

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
    
  get_ss_vs_db_missing_rows: () ->
    ss_missing = []
    db_map = {}
    for k,v of @db_member_map
      db_map[k] = v
    for ss_row in @ss_memberlist
      id = ss_row.db_id
      if id
        delete db_map[id]
      else
        ss_missing.push(ss_row)
    db_missing = (item for id, item of db_map)
    return [ss_missing, db_missing]
      
################################################################################
# View - JQuery interactions with the html
################################################################################

class WSRC_admin_memberlist_view
  
  constructor: () ->
    $("#tabs")
      .tabs()
      .removeClass("initiallyHidden")
    @db_member_table_body = $("#db_memberlist table.memberlist tbody")
    @ss_member_table_body = $("#ss_memberlist table.memberlist tbody")
    @ss_vs_db_table_head  = $("#ss_vs_db_diff table.differences thead")
    @ss_vs_db_table_body  = $("#ss_vs_db_diff table.differences tbody")
    @ss_vs_db_missing_from_db_body  = $("#ss_vs_db_diff table.missing_from_db tbody")
    @ss_vs_db_missing_from_ss_body  = $("#ss_vs_db_diff table.missing_from_ss tbody")
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

  get_display_col: (db_field) ->
    cls = field = ''
    for spec in @db_membership_colspec
      if db_field == spec[2]
        cls = spec[0]
        field = spec[1]
        break
    return [cls, field]
    
  add_to_table: (table_body, col_spec, row) ->
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
          
  add_db_member: (member, table_body) ->
    table_row = @add_to_table(table_body, @db_membership_colspec, member)
    return true

  add_ss_member: (member, table_body, callback) ->
    unless table_body
      table_body = @ss_member_table_body
    row = @add_to_table(table_body, @ss_membership_colspec, member)
    if callback
      callback(row)
    return true

  add_ss_vs_db_diff_col: (cls, field) ->
    @ss_vs_db_table_head.append("<th class='#{ cls }'>#{ field }</th>")
    return true

  add_ss_vs_db_diff_row: (id, row) ->
    new_row = ""
    for val in row
      if val
        [cls, field, val] = val
        new_row += "<td class='#{ cls }' data-field='#{ field }'>#{ val }</td>"
      else
        new_row += "<td></td>"
    @ss_vs_db_table_body.append("<tr data-id='#{ id }'>#{ new_row }</tr>")
    return true
    
  show_change_member_details_form: (field, new_val, submit_path, id, row_id) ->
    jqdialog = $("#change_member_form_dialog")
    jqform = jqdialog.find("form")
    jqform.find("div.ui-field-contain").hide()
    jqform.data("field", field)
    jqform.data("path", submit_path)
    jqform.data("id", id)
    jqform.data("row_id", row_id)
    
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
    jqinput = jqform.find("[name='#{ field }']")
    val = jqinput.val()
    return [field, val, path, id, row_id]
    
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
      save_member_details: (evt) =>
    
    @view = new WSRC_admin_memberlist_view(callbacks)
    [missing_from_db, missing_from_ss] = model.get_ss_vs_db_missing_rows()
    missing_from_db = (x for x in missing_from_db when x.active?.toLowerCase()[0] == 'y')
    missing_from_ss = (x for x in missing_from_ss when x.user.is_active)

    add_button_callback = (table_row) ->
      table_row.append("<td><button onclick='wsrc.admin.memberlist.on(\"show_new_member_form\", this)'>Add</button></td>")
      id = table_row.find("td.index").text()
      if id
        table_row.attr("id", "added_member_#{ id }")

    for member in @model.db_memberlist
      @view.add_db_member(member, @view.db_member_table_body)
    for member in missing_from_ss
      @view.add_db_member(member, @view.ss_vs_db_missing_from_ss_body)
      
    for member in @model.ss_memberlist
      @view.add_ss_member(member)
    for member in missing_from_db
      @view.add_ss_member(member, @view.ss_vs_db_missing_from_db_body, add_button_callback)
      
    wsrc.utils.apply_alt_class(@view.db_member_table_body.children(), "alt")
    wsrc.utils.apply_alt_class(@view.ss_member_table_body.children(), "alt")
    wsrc.utils.apply_alt_class(@view.ss_vs_db_missing_from_db_body.children(), "alt")
    wsrc.utils.apply_alt_class(@view.ss_vs_db_missing_from_ss_body.children(), "alt")

    dblclick_handler = (evt) =>
      id = $(evt.target).parents("tr").data("id")
      player = @model.db_member_map[id]
      if player
        url = "/admin/auth/user/#{ player.user.id }/"
        window.open(url, "_blank")

    @view.db_member_table_body.children().dblclick(dblclick_handler)
    @view.ss_vs_db_missing_from_ss_body.children().dblclick(dblclick_handler)

    wsrc.utils.configure_sortables()
    @populate_diff_table()
    @view.ss_vs_db_table_body.find("td.id_field").dblclick(dblclick_handler)

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
      successCB: (xhr, status) =>
        jqmask.unmask()
        @view.hide_new_member_form()
        $("tr#added_member_#{ player_obj.wsrc_id }").remove()        
        wsrc.utils.apply_alt_class(@view.ss_vs_db_missing_from_db_body.children(), "alt")
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to add new user.")
    player_obj.user = user_obj
    jqmask.mask("Creating new user...")
    wsrc.ajax.ajax_bare_helper("/data/memberlist/player/", player_obj, opts, "POST")

  diff_right_click_handler: (evt) ->
    jtarget = $(evt.target)
    jcell   = jtarget.parents("td")
    jrow    = jtarget.parents("tr")
    id      = wsrc.utils.to_int(jrow.data("id"))
    field   = jcell.data("field")
    from    = jcell.find("div.from").text()
    to      = jcell.find("div.to").text()
    if field.startsWith("user.")
      player = @model.db_member_map[id]
      obj_id = player.user.id
      path = "/data/memberlist/user/#{ id }"
      field = field.replace("user.", "") 
    else
      path = "/data/memberlist/player/#{ id }"
      obj_id = id
    @view.show_change_member_details_form(field, to, path, obj_id, id)

  change_member_submit_handler: () ->
    [field, val, path, id, row_id] = @view.get_changed_member_details()
    data = {id: id}
    data[field] = val
    jrow = @view.ss_vs_db_table_body.find("tr").filter (idx, elt) -> $(elt).data("id") == row_id
    jcell = jrow.find("td").filter (idx, elt) -> $(elt).data("field") == field
    jqmask  = $("body")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      successCB: (xhr, status) =>
        @view.hide_change_member_form()
        jqmask.unmask()
        jcell.children().remove()
        jcell.off('contextmenu')
        if 0 == jrow.find("div.to").length
          jrow.remove()
          wsrc.utils.apply_alt_class(@view.ss_vs_db_table_body.children(), "alt")
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to update user.")
    jqmask.mask("Updating user details...")
    wsrc.ajax.ajax_bare_helper(path, data, opts, "PATCH")

  populate_diff_table: () ->
    diff_cols = {}
    for id, row of @model.ss_vs_db_diffs
      for field, diff of row
        diff_cols[field] = field
    diff_cols = (c[2] for c in @view.db_membership_colspec when c[2] of diff_cols) # order cols consistently with main table
    diff_cols = ([c, @view.get_display_col(c)[0], @view.get_display_col(c)[1]] for c in diff_cols)
    @view.add_ss_vs_db_diff_col("", "Record")
    for [field, cls, display] in diff_cols
      @view.add_ss_vs_db_diff_col('', display)
    for db_record in @model.db_memberlist
      id = db_record.id
      row = @model.ss_vs_db_diffs[id]
      unless row
        continue
      row_vals = [["text id_field", null, "<div>#{ db_record.user.last_name }, #{ db_record.user.first_name }</div>"]]
      for [field, cls] in diff_cols
        diff = row[field]
        if diff          
          row_vals.push(["#{ cls } diff_field", field, "<div class='from'>#{ row[field][1] }</div><div class='to'>#{ row[field][0] }</div>"])
        else
          row_vals.push(null)
      @view.add_ss_vs_db_diff_row(id, row_vals)
    wsrc.utils.apply_alt_class(@view.ss_vs_db_table_body.children(), "alt")
    @view.ss_vs_db_table_body.find("td.diff_field").on('contextmenu', (evt) =>
      evt.preventDefault();
      @diff_right_click_handler(evt)
      return false;
    )    
      
  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: (db_memberlist, ss_memberlist, ss_vs_db_diffs) ->
    model = new WSRC_admin_memberlist_model(db_memberlist, ss_memberlist, ss_vs_db_diffs)
    @instance = new WSRC_admin_memberlist(model)


admin = wsrc.utils.add_object_if_unset(window.wsrc, "admin")
admin.memberlist = WSRC_admin_memberlist

              
