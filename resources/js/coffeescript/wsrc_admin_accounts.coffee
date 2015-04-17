
class WSRC_admin_accounts 


  constructor: (category_list, @transaction_list) ->
    @jq_account_transactions_tbody = $('#transactions_tab table.transactions tbody')
    @jq_upload_transactions_tbody = $('#upload_tab table.transactions tbody')
    @jq_summary_tbody = $("#transactions_tab .information-table tbody")
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
    @jq_summary_tbody.sortable(
      items: "> #{ @data_row_selector }"
      placeholder: "ui-state-highlight"
    ).disableSelection()

    balance = 0
    for transaction in @transaction_list
      balance += transaction.amount
      transaction.balance = balance
      
    @set_transaction_summary()

    
    dialog = $( "#swing-transaction-dialog" ).dialog(
      autoOpen: false
      height: "auto"
      width: "32em"
      modal: true
      buttons: 
        Create: () =>
          @create_swing_transaction.call(this)
        Cancel: () ->
          dialog.dialog("close")
    )
 
    form = dialog.find("form").on("submit", (event) ->
      event.preventDefault()
      @create_swing_transaction()
    )

    $(document).keydown( (e) ->
      if e.ctrlKey and e.which == 66 # 'b' key 
        e.preventDefault()
        dialog.find("select").val("")
        dialog.find("input[name='amount']").val("0.0")
        dialog.find("input[name='comment']").val('')
        dialog.dialog("open")
        return false
    )


  update_category_map: (category_list) ->
    @categories = {}
    for category in category_list
      @categories[category.id] = category
    category_list.sort (lhs, rhs) ->
      wsrc.utils.lexical_sorter(lhs, rhs, (x) -> x.description)
    jq_selects = @jq_upload_transactions_tbody.find(@data_row_selector).find("select[name='category']")
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
    alt = false
    @jq_summary_tbody.children().remove()
    for category in category_list
      jq_row = $("<tr data-id='#{ category.id }'><td class='category'><input type='checkbox'> #{ category.description }</td><td class='count'> <td class='incoming'> <td class='outgoing'> <td class='net_total'> </tr>")
      jq_row.find("input[type='checkbox']").on("change", () => @add_transaction_rows.call(this))
      if alt
        jq_row.addClass('alt')
        alt = false
      else
        alt = true
      @jq_summary_tbody.append(jq_row)
      
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
    rows = @jq_upload_transactions_tbody.find(@data_row_selector)
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

  get_transaction_filter: () ->
    start_date = $("#transactions_start_date_input").datepicker("getDate")
    end_date = $("#transactions_end_date_input").datepicker("getDate")
    date_type = $("input[name='transactions_date_type']:checked").val()
    categories = []
    @jq_summary_tbody.children().each (idx, elt) ->
      jq_row = $(elt)
      if jq_row.find("td.category input[type='checkbox']").prop('checked')
        categories.push(parseInt(jq_row.data('id')))
    return (transaction) ->
      date = transaction[date_type]
      if date
        date = wsrc.utils.iso_to_js_date(date)
        if date <= end_date and date >= start_date
          if categories.length == 0 or transaction.category in categories
            return true
      return false

  set_transaction_summary: () ->
    start_date = $("#transactions_start_date_input").datepicker("getDate")
    end_date = $("#transactions_end_date_input").datepicker("getDate")
    summary = @summarise_transactions(@transaction_list, start_date, end_date)
    @jq_summary_tbody.children().each (idx, elt) ->
      jq_row = $(elt)
      cat_id = parseInt(jq_row.data('id'))
      cat_summary = summary.category_totals[cat_id]
      unless cat_summary
        cat_summary = {count: 0, incoming: 0, outgoing: 0, net_total: 0}
      jq_row.find("td.count").text(cat_summary.count)
      jq_row.find("td.incoming").text(cat_summary.incoming.toFixed(2))
      jq_row.find("td.outgoing").text(cat_summary.outgoing.toFixed(2))
      jq_net_total = jq_row.find("td.net_total").text(cat_summary.net_total.toFixed(2))
      if cat_summary.net_total > 0
        jq_net_total.removeClass('debit').addClass('credit')
      else if cat_summary.net_total < 0
        jq_net_total.addClass('debit').removeClass('credit')
      else
        jq_net_total.removeClass('debit').removeClass('credit')
    @add_transaction_rows()

  add_transaction_rows: () ->
    alt_row = false
    @jq_account_transactions_tbody.children().remove()
    date_type = $("input[name='transactions_date_type']:checked").val()
    date_order = $("input[name='transactions_date_ordering']:checked").val()
    filter = @get_transaction_filter()
    record_list = (rec for rec in @transaction_list when filter(rec))
    if date_type == 'date_issued'
      record_list.sort (lhs, rhs) =>
        cmp = wsrc.utils.iso_to_js_date(lhs.date_issued) - wsrc.utils.iso_to_js_date(rhs.date_issued)
        if cmp == 0
          cmp = @categories[lhs.category].ordering - @categories[rhs.category].ordering
        return cmp
    
    for record in record_list
      jq_row = @transaction_record_to_row(record, date_type == 'date_cleared')
      if alt_row
        jq_row.addClass('alt')
        alt_row = false
      else
        alt_row = true
      @jq_account_transactions_tbody.append(jq_row)
      jq_row.dblclick( (e) =>
        jq_row = $(e.delegateTarget)
        url = "/admin/accounts/transaction/#{ jq_row.data('id') }"
        window.open(url, "_blank")
      )
    container = @jq_account_transactions_tbody.parents("div.container")
    outer_container1 = container.parent()
    outer_container2 = outer_container1.parent()
    tab_bar = outer_container2.find("ul.ui-tabs-nav")
    fieldset = outer_container1.find("fieldset")
    calc = -30 + outer_container2.height() - tab_bar.outerHeight(true) - fieldset.outerHeight(true) 
    container.css("max-height", "#{ calc }px")
    
  transaction_record_to_row: (record, with_balance) ->
    toBritish = (record, field) ->
      str = record[field]
      unless str
        return ""
      chop = (start, len) -> str.substr(start, len)
      "#{ chop(8,2) }/#{ chop(5,2) }/#{ chop(0,4) }"
    credit_or_debit = (record, field) ->
      val = parseFloat(record[field])
      if val < 0 then "debit" else "credit"
    str = (record, field) ->
      val = record[field]
      if val then val else ""
    ccy = (record, field) ->
      val = parseFloat(record[field])
      val.toFixed(2)
    category_name = (record, field) =>
      id = parseInt(record[field])
      @categories[id].description
    mapping = [
      ['date_issued',  toBritish]
      ['date_cleared', toBritish]
      ['bank_code',    str]
      ['bank_number',  str]
      ['bank_memo',    str]
      ['comment',      str]
      ['category',     category_name]
      ['amount',       ccy, credit_or_debit]
    ]
    if with_balance
      mapping.push(['balance', ccy])
    jq_row = $("<tr data-id='#{ record.id }'></tr>")
    for data in mapping
      field = data[0]
      value = data[1](record, field)
      extra_classes = ""
      if data.length == 3
        extra_classes = data[2](record, field)
      jq_row.append("<td class='#{ field } #{ extra_classes }'>#{ value }</td>")
    return jq_row
    
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

  get_upload_transaction_data: (start_date, end_date) ->
    rows = @jq_upload_transactions_tbody.find(@data_row_selector)
    transactions = []
    rows.each (idx, elt) =>
      transaction = @row_to_transaction_record($(elt))
      date = wsrc.utils.iso_to_js_date(transaction.date_issued)
      if date >= start_date and date <= end_date  
        transactions.push(transaction)
    return transactions    
        
  upload_transactions: () ->
    start_date = $("#upload_start_date_input").datepicker("getDate")
    end_date   = $("#upload_end_date_input").datepicker("getDate")
    data =
      transactions: @get_upload_transaction_data(start_date, end_date)
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
    
  summarise_transactions: (transactions, start_date, end_date, use_cleared_date) ->
    incoming = 0.0
    outgoing = 0.0
    count = 0
    min_date = end_date
    max_date = start_date
    category_totals = {}
    get_category = (cat_id) ->
      return wsrc.utils.get_or_add_property(category_totals, cat_id, () -> {count: 0, incoming: 0, outgoing: 0, net_total: 0.0})
    for transaction in transactions    
      date = if use_cleared_date then transaction.date_cleared else transaction.date_issued
      date = wsrc.utils.iso_to_js_date(date)
      if date >= start_date and date <= end_date
        if date > max_date
          max_date = date
        if date < min_date
          min_date = date
        if transaction.category.length == 0
          transaction.category = "undefined"
        cat_summary = get_category(transaction.category)
        cat_summary.count += 1
        if not isNaN(transaction.amount)
          cat_summary.net_total += transaction.amount
          if transaction.amount > 0
            incoming += transaction.amount
            cat_summary.incoming += transaction.amount
          else 
            outgoing += transaction.amount
            cat_summary.outgoing += transaction.amount * -1.0
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
      transactions = @get_upload_transaction_data(start_date, end_date)
      summary = @summarise_transactions(transactions, start_date, end_date)
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

  @onReady: (initial_categories, initial_transactions) ->
    $("input.datepicker").datepicker().datepicker("option", "dateFormat", "dd/mm/yy")
    today = new Date()
    three_months_back = new Date(today.getYear() + 1900, today.getMonth()-3, today.getDate())
    $("input.datepicker-three-months").datepicker("setDate", three_months_back)
    $("input.datepicker-today").datepicker("setDate", today)

    @instance = new WSRC_admin_accounts(initial_categories, initial_transactions)
    @instance.apply_categories()
    
    $("#tabs")
      .tabs()
      .removeClass("initiallyHidden")
    $(".radio-buttonset").buttonset()
    $(".button-bar > input[type='button']").button()
    $('.information-set input').attr('readonly', true)    

    start_date = new Date(0)
    end_date   = new Date(2099, 1, 1)
    upload_transactions = @instance.get_upload_transaction_data(start_date, end_date)
    summary = @instance.summarise_transactions(upload_transactions, start_date, end_date)
    $("#upload_start_date_input").datepicker("setDate", summary.min_date)
    $("#upload_end_date_input").datepicker("setDate", summary.max_date)
    @instance.handle_upload_data_changed(summary)
    return null
    
admin = wsrc.utils.add_object_if_unset(window.wsrc, "admin")
admin.accounts = WSRC_admin_accounts

