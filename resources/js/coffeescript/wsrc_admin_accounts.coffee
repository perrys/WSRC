
class WSRC_admin_accounts 


  constructor: (category_list) ->
    @jq_transactions_tbody = $('table.transactions tbody')
    @jq_category_tbody = $('table.categories tbody')
    @data_row_selector = 'tr:not(.header)'
    
    @update_category_map(category_list)
    @jq_category_tbody.sortable(
      disabled: true
      items: "> #{ @data_row_selector }"
      placeholder: "ui-state-highlight"
      update: () =>
        @handle_category_order_updated.call(this)
    ).disableSelection()
    @add_category_rows(category_list)

  update_category_map: (category_list) ->
    @categories = {}
    for category in category_list
      @categories[category.id] = category
    category_list.sort (lhs, rhs) ->
      wsrc.utils.lexical_sorter(lhs, rhs, (x) -> x.description)
    jq_selects = @jq_transactions_tbody.find(@data_row_selector).find("select[name='category']")
    # add new categories and remove obsolete ones, but leave existing as they may have been manually selected
    jq_selects.each (idx, elt) =>
      jq_select = $(elt)
      options = jq_select.children()      
      options.each (idx, elt) =>
        if idx > 0 # skip blank option
          unless @categories[parseInt(elt.value)]
            elt.parentElement.removeChild(elt)
      for category in category_list
        unless jq_select.find("option[value='#{ category.id }']").length > 0
          jq_select.append("<option value='#{ category.id }'>#{ category.description }</option>")
    
  toggle_category_edit_mode: (elt) ->
    mode = $(elt).parent().find("input[name='#{ elt.name }']:checked").val()
    button_selector = "#categories_tab .button-bar "
    if mode == "edit"
      @jq_category_tbody.find('.edit').add(button_selector + ".edit").show()
      @jq_category_tbody.find('.view').add(button_selector + ".view").hide()
      @jq_category_tbody.sortable('enable')
    else
      @jq_category_tbody.find('.edit').add(button_selector + ".edit").hide()
      @jq_category_tbody.find('.view').add(button_selector + ".view").show()
      @jq_category_tbody.sortable('disable')
      @reset_categories(@apply_categories)

  handle_category_order_updated: () ->
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

    records.sort (lhs, rhs) ->
      return lhs.ordering - rhs.ordering
    for record in records
      @add_category_row(record)
     
  reset_categories: (callback) ->
    rows = @jq_category_tbody.find(@data_row_selector)
    records = []
    for row in rows
      record = {}
      for field in ["name", "description", "regex"]
        record[field] = $(row).find("input[name='#{ field }']").val()
      record.id = parseInt($(row).data('id'))
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
        @update_category_map(data)
        @add_category_rows(data, true)
        if callback
          callback.apply(this)
    jqmask.mask("Updating...")
    wsrc.ajax.ajax_bare_helper("/data/accounts/category/", records, opts, "PUT")

  save_category: (ui) ->
    row = $(ui).parents('tr')
    id = parseInt(row.data("id"))
    record = @categories[id]
    for field in ["name", "description", "regex"]
      input = row.find("input[name='#{ field }']")
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
    wsrc.ajax.ajax_bare_helper("/data/accounts/category/#{ id }/", record, opts, "PATCH")

  apply_categories: () ->
    test_list = []
    for id, category_object of @categories
      try
        test_list.push([id, new RegExp(category_object.regex), category_object.ordering])
      catch error
        alert(error)
    test_list.sort((lhs, rhs) -> lhs[2] - rhs[2])
    rows = @jq_transactions_tbody.find(@data_row_selector)
    set_category = (row, id) ->
      row.find('select').val(id)
    for row in rows
      row = $(row)
      for [id, regex] in test_list
        found = false
        for field in ['bank_memo', 'comment']
          td_field = row.find("td.#{ field }")
          input = td_field.find("input")
          text = if input.length > 0 then input.val() else td_field.text()
          if regex.test(text) 
            set_category(row, id)
            found = true
            break
        if found
          break

  row_to_transaction_record: (jq_row) ->
    toISO = (jq_elt) ->
      str = jq_elt.text()
      if str == "null"
        return null
      chop = (start, len) -> str.substr(start, len)
      "#{ chop(6,4) }-#{ chop(3,2) }-#{ chop(0,2) }"
    parse_float_or_zero = (jq_elt) ->
      val = parseFloat(jq_elt.text())
      return if isNaN(val) then 0 else val
    parse_int_or_null = (jq_elt) ->
      str = jq_elt.text()
      if str.length == 0
         return null
      val = parseInt(str)
      return if isNaN(val) then null else val
    text_value = (jq_elt) ->
      jq_elt.text()
    input_value = (jq_elt) ->
      jq_elt.find('input').val()
    select_value = (jq_elt) ->
      jq_elt.find('select').val()
    mapping = [
      ['date_issued',  toISO]
      ['date_cleared', toISO]
      ['amount',       parse_float_or_zero]
      ['bank_number',  parse_int_or_null]
      ['bank_memo',    text_value]
      ['comment',      input_value]
      ['category',     select_value]
    ]
    transaction = {}
    for m in mapping
      field = m[0]
      map_func = m[1]
      transaction[field] = map_func(jq_row.find("td.#{ field }"))
    return transaction
        
  upload_transactions: () ->
    start_date = $("#upload_start_date_input").datepicker("getDate")
    end_date   = $("#upload_end_date_input").datepicker("getDate")
    rows = @jq_transactions_tbody.find(@data_row_selector)
    transactions = []
    rows.each (idx, elt) =>
      transactions.push(@row_to_transaction_record($(elt)))
    data =
      transactions: transactions
      account: parseInt($("#upload_account_selector").val())
    csrf_token = $("input[name='csrfmiddlewaretoken']").val()
    jqmask = $("body")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\Update failed.")
      successCB: (data, status, jq_xhr) =>
        jqmask.unmask()
    jqmask.mask("Updating...")
    account = $("#upload_account_selector").val()
    wsrc.ajax.ajax_bare_helper("/data/accounts/account/#{ account }/transactions/", data, opts, "PUT")
    
  sumarize_transactions: (start_date, end_date) ->
    rows = @jq_transactions_tbody.find(@data_row_selector)
    incoming = 0.0
    outgoing = 0.0
    count = 0
    min_date = end_date
    max_date = start_date
    category_totals = {}
    get_category = (cat_name) ->
      return wsrc.utils.get_or_add_property(category_totals, cat_name, () -> {count: 0, total: 0.0})
    rows.each (idx, elt) ->
      row = $(elt)
      date = wsrc.utils.british_to_js_date(row.find("td.date_issued").text())
      if date >= start_date and date <= end_date
        if date > max_date
          max_date = date
        if date < min_date
          min_date = date
        amount = parseFloat(row.find("td.amount").text())
        category = row.find("td.category select").val()
        if category.length == 0
          category = "undefined"
        cat_summary = get_category(category)
        cat_summary.count += 1
        if not isNaN(amount)
          cat_summary.total += amount
          if amount > 0
            incoming += amount
          else
            outgoing += amount
        count += 1
    return {
      incoming: incoming
      outgoing: outgoing * -1.0
      count: count
      category_totals: category_totals
      max_date: max_date
      min_date: min_date
    }

  handle_upload_data_changed: (summary) ->
    unless summary
      start_date = $("#upload_start_date_input").datepicker("getDate")
      end_date   = $("#upload_end_date_input").datepicker("getDate")
      summary = @sumarize_transactions(start_date, end_date)
    $("#upload_transaction_count_input").val(summary.count)
    $("#upload_incoming_input").val(summary.incoming.toFixed(2))
    $("#upload_outgoing_input").val(summary.outgoing.toFixed(2))
    uncategorized = summary.category_totals["undefined"]?.count
    if uncategorized
      $("#upload_uncategorized_count_input").val(uncategorized)
      $("#upload_uncategorized_count_input").parents("div.ui-field-contain").show()
      $("#upload_go_button").attr('disabled', true)
    else
      $("#upload_uncategorized_count_input").parents("div.ui-field-contain").hide()
      $("#upload_go_button").attr('disabled', false)
        
  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: (initial_categories) ->
    @instance = new WSRC_admin_accounts(initial_categories)
    @instance.apply_categories()
    
    $("#tabs")
      .tabs()
      .removeClass("initiallyHidden")
    $(".radio-buttonset").buttonset()
    $(".button-bar > input[type='button']").button()
    $("input[class='datepicker']").datepicker().datepicker("option", "dateFormat", "dd/mm/yy")
    $('.information-set input').attr('readonly', true)    

    summary = @instance.sumarize_transactions(new Date(0), new Date(2099, 1, 1))
    $("#upload_start_date_input").datepicker("setDate", summary.min_date)
    $("#upload_end_date_input").datepicker("setDate", summary.max_date)
    @instance.handle_upload_data_changed(summary)
    return null
    
admin = wsrc.utils.add_object_if_unset(window.wsrc, "admin")
admin.accounts = WSRC_admin_accounts

