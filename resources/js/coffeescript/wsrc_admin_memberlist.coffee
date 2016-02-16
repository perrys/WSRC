
  
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

  @diff_row_blank_test: (data_row) ->
    blank_row = true
    for field, val of data_row
      if field == "user"
        user = val
        for field, val of user
          if val != null
            blank_row = false
            break
      else if field != "id" and field != "ordered_name" and val != null
        blank_row = false
        break
    return blank_row
    
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

  @yes_or_no_renderer: (data, type, row) ->
    lookup = { true: 'yes', false: 'no', null: '' }
    lookup[data]

  constructor: (@callbacks) ->
    $("#tabs")
      .tabs()
      .removeClass("initiallyHidden")

    alignment =
      text: 'dt-body-left'
      number: 'dt-body-right'
    yesno   = WSRC_admin_memberlist_view.yes_or_no_renderer
    memtype = WSRC_admin_memberlist_model.get_membership_type_display_name

    db_membership_api_colspec = [
      {className: alignment.text,   title: 'Last Name',       data: 'user.last_name'},
      {className: alignment.text,   title: 'First Name',      data: 'user.first_name'},
      {className: alignment.text,   title: 'Active',          data: 'user.is_active',  render: yesno,   searchable: false},
      {className: alignment.text,   title: 'Mem. Type',       data: 'membership_type', render: memtype, searchable: false},
      {className: alignment.text,   title: 'E-Mail',          data: 'user.email'},
      {className: alignment.text,   title: 'Receive?',        data: 'prefs_receive_email', render: yesno, searchable: false},
      {className: alignment.number, title: 'WSRC ID',         data: 'wsrc_id'},
      {className: alignment.number, title: 'Door Card #',     data: 'cardnumber'},
      {className: alignment.number, title: 'SquashLevels ID', data: 'squashlevels_id'},
      {className: alignment.number, title: 'Mobile',          data: 'cell_phone'},
      {className: alignment.number, title: 'Other Phone',     data: 'other_phone'},
      {className: alignment.number, title: 'Id',              data: 'id', name: 'id', visible: false, searchable: false},
    ]

    ss_membership_api_colspec = [
      {className: alignment.text,   title: 'Surname',    data: 'surname'},
      {className: alignment.text,   title: 'First Name', data: 'firstname'},
      {className: alignment.text,   title: 'Active',     data: 'active', searchable: false},
      {className: alignment.text,   title: 'Category',   data: 'category', searchable: false},
      {className: alignment.text,   title: 'E-Mail',     data: 'email'},
      {className: alignment.text,   title: 'Receive?',   data: 'Data Prot email', searchable: false},
      {className: alignment.number, title: 'WSRC ID',    data: 'index'},
      {className: alignment.number, title: 'Cardnumber', data: 'cardnumber'},
      {className: alignment.number, title: 'Mobile',     data: 'mobile_phone'},
      {className: alignment.number, title: 'Home Phone', data: 'home_phone'},
    ]

    bs_membership_api_colspec = [
      {className: alignment.text,   title: 'Last Name',   data: 'last_name'},
      {className: alignment.text,   title: 'First Name',  data: 'first_name'},
      {className: alignment.text,   title: 'EMail',       data: 'Email address'},
      {className: alignment.number, title: 'Mobile',      data: 'Mobile'},
      {className: alignment.number, title: 'Telephone',   data: 'Telephone'},
    ]

    diff_renderer = (data, type, row) ->
      if type != 'display'
        return data
      if data
        return "<div data-field='#{ data.field }'><div class='from'>#{ data.from }</div><div class='to'>#{ data.to }</div></div>"
      return ''
      
    augment_to_diff_spec = (spec) ->
      if spec.name == 'id'
        return spec
      newspec = {name: spec.data}
      for k, v of spec
        newspec[k] = v
      newspec.render = diff_renderer
      return newspec
      
    differences_api_colspec = (augment_to_diff_spec(item) for item in db_membership_api_colspec)
    differences_api_colspec.unshift({className: alignment.text,   title: 'Record',    data: 'ordered_name'})
    
    spec_map =
      "memberlist-db": db_membership_api_colspec 
      "memberlist-ss": ss_membership_api_colspec
      "memberlist-bs": bs_membership_api_colspec
      "differences":   differences_api_colspec
      
    fullpage_length_menu = [[-1, 10, 25, 50], ["All", 10, 25, 50]]
    paged_length_menu    = [[10, 25, 50, -1], [10, 25, 50, "All"]]
    
    for cls, spec of spec_map
      $("table.#{ cls }").each (idx, elt) =>
        jqtable = $(elt)
        options =
          lengthMenu: if jqtable.hasClass("fullpage") then fullpage_length_menu else paged_length_menu
          jqueryUI: true
          autoWidth: false
          columns: spec
        jqtable.DataTable(options)
        if cls == "memberlist-db"
          jqtable.find('tbody').on('dblclick',    "tr",      @callbacks.id_row_open_admin_click_handler)
        if cls == "memberlist-ss" and jqtable.hasClass("missing-from-db")          
          jqtable.find('tbody').on('contextmenu', "tr",      @callbacks.open_new_member_handler)
        else if cls == "differences"
          jqtable.find('tbody').on('dblclick',    "tr",       @callbacks.id_row_open_admin_click_handler)
          jqtable.find('tbody').on('contextmenu', "div.from", @callbacks.open_change_details_handler)    
          jqtable.find('tbody').on('contextmenu', "div.to",   @callbacks.open_change_details_handler)    

  get_table_api: (tab_id, table_class) ->
    jqtable = $("##{ tab_id } table.#{ table_class }")
    return jqtable.DataTable({retrieve: true})

  get_comparison_table: (tab_id, table_class) ->
    return $("##{ tab_id } table.#{ table_class }")

  populate_differences_tab: (tab_id, missing_from_db_list, missing_from_other_list, differences) ->
    for jq in [$("##{ tab_id }"), $("li[aria-controls='#{ tab_id }']")]
      jq.removeClass('ui-helper-hidden')
    missing_from_db_api    = @get_table_api(tab_id, "missing-from-db")
    missing_from_other_api = @get_table_api(tab_id, "missing-from-other")
    differences_api        = @get_table_api(tab_id, "differences")

    missing_from_db_api.rows.add(missing_from_db_list).draw()    
    missing_from_other_api.rows.add(missing_from_other_list).draw()

    diff_cols = {}
    for id, row of differences
      for field, diff of row
        diff_cols[field] = field
        
    for id,diffs of differences
      unless diffs
        continue
      db_record = @callbacks.lookup_db_member(id)
      diff_row = {ordered_name: db_record.ordered_name}
      for field, val of db_record
        if field == 'ordered_name' or field == 'id'
          diff_row[field] = val
        else if field == 'user'
          diff_row.user = {}
          user = val
          for field, val of user
            user_field = "user.#{ field }"
            if user_field of diffs
              diff = diffs[user_field]
              val = {field: user_field, to: diff[0], from: diff[1]}
            else
              val = null
            diff_row.user[field] = val
        else
          if field of diffs
            diff = diffs[field]
            val = {field: field, to: diff[0], from: diff[1]}
          else
            val = null
          diff_row[field] = val
      differences_api.row.add(diff_row)
    differences_api.draw()

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
      modal: true
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
    
  show_new_member_form: (user_obj, player_obj, source_div_id) ->
    jqdialog = $("#new_member_form_dialog")
    jqform  = jqdialog.find("form")
    jqform.data("source_div_id", source_div_id)    
    for key, val of user_obj
      jqform.find("fieldset.user [name='#{ key }']").val("#{ val }")
    for key, val of player_obj
      jqform.find("fieldset.player [name='#{ key }']").val("#{ val }")
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
    jqform  = jqdialog.find("form")
    source  = jqform.data("source_div_id")
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
      user_obj[key] = jqform.find("fieldset.user [name='#{ key }']").val() or null
    for key,val of player_obj
      val = jqform.find("fieldset.player [name='#{ key }']").val()
      if val
        player_obj[key] = val
    return [user_obj, player_obj, source]  
    

################################################################################
# Controller - initialize and respond to events
################################################################################

class WSRC_admin_memberlist 

  constructor: (@model) ->

    me = this
    callbacks = 
      id_row_open_admin_click_handler: (evt) ->
        jqrow = $(this)
        data = WSRC_admin_memberlist.get_data_for_jqrow(jqrow)
        me.open_user_admin_page(data.id)
      open_change_details_handler: (evt) ->
        jqsrc = $(this)
        evt.preventDefault()
        me.open_change_details_handler(jqsrc)
        return false
      open_new_member_handler: (evt) ->
        jqrow = $(this)
        evt.preventDefault()
        me.show_new_member_form(jqrow)
        return false
        
      lookup_db_member: (id) => @model.db_member_map[id]

    @view = new WSRC_admin_memberlist_view(callbacks)
    
    @view.get_table_api("db_memberlist", "memberlist-db").rows.add(@model.db_memberlist).draw()
    if model.ss_memberlist
      @view.get_table_api("ss_memberlist", "memberlist-ss").rows.add(@model.ss_memberlist).draw()
    
    [missing_from_db, missing_from_ss] = model.get_ss_vs_db_missing_rows()
    missing_from_db = (x for x in missing_from_db when x.active?.toLowerCase()[0] == 'y')
    missing_from_ss = (x for x in missing_from_ss when x.user.is_active)

    @view.populate_differences_tab("ss_vs_db_diffs", missing_from_db, missing_from_ss, @model.ss_vs_db_diffs)

    $("form#booking_system_credentials").on("submit", () => @booking_system_fetch_memberlist_handler())
        
  booking_system_update_tables: (data) ->
    @model.set_bs_memberlist(data.contacts, data.diffs)
    
    @view.get_table_api("bs_memberlist", "memberlist-bs").rows.add(@model.bs_memberlist).draw()
      
    [missing_from_db, missing_from_bs] = @model.get_bs_vs_db_missing_rows()
    missing_from_bs = (x for x in missing_from_bs when x.user.is_active)
    
    @view.populate_differences_tab("bs_vs_db_diffs", missing_from_db, missing_from_bs, @model.bs_vs_db_diffs)


  show_new_member_form: (jqrow) ->
    source    = jqrow.parents("div.comparison_wrapper").attr("id")
    data_vals = WSRC_admin_memberlist.get_data_for_jqrow(jqrow)
    user_obj  =
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
    @view.show_new_member_form(user_obj, player_obj, source)

  new_member_submit_handler: () ->
    [user_obj, player_obj, source_div_id] = @view.get_new_member_details()
    csrf_token = $("input[name='csrfmiddlewaretoken']").val()
    jqmask = $("body")
    jtable      = @view.get_comparison_table(source_div_id, "missing-from-db")
    table_api   = jtable.DataTable({retrieve: true})
    row         = table_api.row (idx, data, node) -> data.index == wsrc.utils.to_int(player_obj.wsrc_id)
    
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      successCB: (data, status, jq_xhr) =>
        jqmask.unmask()
        @view.hide_new_member_form()
        row.remove()
        table_api.draw()
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
    
  open_change_details_handler: (jqtarget) ->
    jqparent  = jqtarget.parent()
    jqrow     = jqtarget.parents("tr")
    data_row  = WSRC_admin_memberlist.get_data_for_jqrow(jqrow)
    id        = data_row.id
    field     = jqparent.data("field")
    from      = jqparent.find("div.from").text()
    to        = jqparent.find("div.to").text()
    source    = jqtarget.parents("div.comparison_wrapper").attr("id")
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
    data        = {id: id}
    data[field] = val
    jtable      = @view.get_comparison_table(source_div_id, "differences")
    table_api   = jtable.DataTable({retrieve: true})
    row         = table_api.row (idx, data, node) -> data.id == row_id
    row_data    = row.data()
    data_obj    = row_data
    if path.startsWith("/data/memberlist/user")
      data_obj = data_obj.user
    
    jqmask  = $("body")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      successCB: (data, status, jq_xhr) =>
        @view.hide_change_member_form()
        jqmask.unmask()
        data_obj[field] = null
        row.data(row_data).draw()
        if WSRC_admin_memberlist_model.diff_row_blank_test(row_data)
          row.remove()
          table_api.draw()
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

  @get_data_for_jqrow: (jqrow) ->
    api = jqrow.parents('table').DataTable({retrieve: true})
    return api.row(jqrow).data();
    

admin = wsrc.utils.add_object_if_unset(window.wsrc, "admin")
admin.memberlist = WSRC_admin_memberlist

              
