
class WSRC_admin_accounts 


  constructor: (category_list) ->
    @jq_category_tbody = $('table.categories tbody')
    @data_row_selector = 'tr:not(.header)'
    @update_category_map(category_list)
    @jq_category_tbody.sortable(
      disabled: true
      items: "> #{ @data_row_selector }"
      placeholder: "ui-state-highlight"
      update: @handle_category_order_updated
    ).disableSelection()
    @add_category_rows(category_list)

  update_category_map: (data) ->
    @categories = {}
    for category in data
      @categories[category.id] = category
    
  toggle_category_edit_mode: (elt) ->
    mode = $(elt).parent().find("input[name='#{ elt.name }']:checked").val()
    button_selector = "#categories .button-bar "
    if mode == "edit"
      @jq_category_tbody.find('.edit').add(button_selector + ".edit").show()
      @jq_category_tbody.find('.view').add(button_selector + ".view").hide()
      @jq_category_tbody.sortable('enable')
    else
      @jq_category_tbody.find('.edit').add(button_selector + ".edit").hide()
      @jq_category_tbody.find('.view').add(button_selector + ".view").show()
      @jq_category_tbody.sortable('disable')
      @reset_categories(@apply_categories)

  handle_category_order_updated: (evt, ui) ->
    jq_rows = @jq_category_tbody.find(@data_row_selector)
    jq_rows.each (idx, elt) ->
      $(elt).find('td.order').text(idx+1)

  add_category_row: (row, edit_mode) ->
    idx = @jq_category_tbody.find(@data_row_selector).length
    unless row
      row = {}
      row.name = row.description = row.regex = ''
      row.ordering = idx+1
    cls = if (idx & 1) == 1 then "alt" else ""
    jq_row_elt = $("""
          <tr data-id='#{ row.id }' class='#{ cls }'>
            <td class='order'>#{ row.ordering } <button class='edit' onclick='wsrc.admin.accounts.on('remove_category_row', this);'></button></td>
            <td class='name'><span class='view'>#{ row.name }</span>        <input name='name'        value='#{ row.name }'        class='edit'/></td>
            <td class='desc'><span class='view'>#{ row.description }</span> <input name='description' value='#{ row.description }' class='edit'/></td>
            <td class='regex'><span class='view'>#{ row.regex }</span>       <input name='regex'       value='#{ row.regex }'       class='edit'/></td>
          </tr>
            """)

    if edit_mode    
      jq_row_elt.find('.view').hide()
    else
      jq_row_elt.find('.edit').hide()
    jq_row_elt.find("button").button({icons: {primary: 'ui-icon-close'}})
    @jq_category_tbody.append(jq_row_elt)

  add_category_rows: (records, clear) ->
    if clear
      @jq_category_tbody.find(@data_row_selector).remove()
    for record in records
      @add_category_row(record)
    wsrc.utils.toggle($('table.categories'))
     
  reset_categories: (callback) ->
    rows = @jq_category_tbody.find(@data_row_selector)
    records = []
    for row in rows
      record = {}
      for field in ["name", "description", "regex"]
        record[field] = $(row).find("input[name='#{ field }']").val()
      record.ordering = parseInt($(row).find('td.order').text())
      records.push(record)
    csrf_token = $("input[name='csrfmiddlewaretoken']").val()
    jqmask = $("body")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\Update failed.")
      successCB: (data, status, jq_xhr) =>
        jqmask.unmask()
        @add_category_rows(data, true)
        if callback
          callback()
    jqmask.mask("Updating...")
    wsrc.ajax.ajax_bare_helper("/data/accounts/account/category/", records, opts, "PUT")

  save_category: (ui) ->
    row = $(ui).parents('tr')
    id = parseInt(row.data("id"))
    record = @categories[id]
    for field in ["name", "description", "regex"]
      input = row.find("input[name='#{ field }_#{ id }']")
      value = input.val()
      record[field] = value
      input.siblings("span").text(value)
    csrf_token = $("input[name='csrfmiddlewaretoken']").val()
    jqmask = $("body")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\Update failed.")
      successCB: (xhr, status) =>
        jqmask.unmask()
        wsrc.utils.toggle({target:ui})
    jqmask.mask("Updating...")
    wsrc.ajax.ajax_bare_helper("/data/accounts/account/category/#{ id }", record, opts, "PATCH")

  apply_categories: () ->
    test_list = {}
    for id, category_object of @categories
      try
        test_list[id] = new RegExp(category_object.regex)
      catch error
        alert(error)
    rows = $('.transactions tr.transaction')
    set_category = (row, id) ->
      row.find('select').val(id)
    for row in rows
      row = $(row)
      for id, regex of test_list
        found = false
        for field in ['bank_memo', 'comment']
          text = row.find("td.#{ field }").text()
          if regex.test(text) 
            set_category(row, id)
            found = true
            break
        if found
          break
        
  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: (initial_categories) ->
    @instance = new WSRC_admin_accounts(initial_categories)
    $("#tabs")
      .tabs()
      .removeClass("initiallyHidden")
    $("#categories_edit_toggle").buttonset()
    $(".button-bar > input[type='button']").button()
    @instance.apply_categories()
    
    return null
    
admin = wsrc.utils.add_object_if_unset(window.wsrc, "admin")
admin.accounts = WSRC_admin_accounts

