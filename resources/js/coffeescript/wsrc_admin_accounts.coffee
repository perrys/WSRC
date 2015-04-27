
################################################################################
# Model - contains a local copy of the accounts database
################################################################################
  
class WSRC_admin_accounts_model

  constructor: (category_list, @account_map) ->
    @set_categories(category_list)
    for id, account of @account_map
      WSRC_admin_accounts_model.set_balances(account.transaction_set)

  get_transaction_list: (account_id) ->  
    transactions = @account_map[account_id].transaction_set

  get_account_name: (account_id) ->  
    transactions = @account_map[account_id].name

  get_account_ids: () ->
    return (id for id, account of @account_map)

  set_transaction_list: (account_id, transactions) ->
    WSRC_admin_accounts_model.set_balances(transactions)
    @account_map[account_id].transaction_set = transactions
    
  get_category: (id) ->
    return @category_map[id]

  has_category: (id) ->
    return @category_map[id]?

  set_categories: (category_list) ->
    @category_map = wsrc.utils.map_by_id(category_list)
    return null

  get_id_category_pairs: () ->
    cat_list = ([parseInt(id), cat] for id, cat of @category_map)
    mapper = (pair) ->
      pair[1].description
    cat_list.sort (lhs, rhs) ->
      wsrc.utils.lexical_sort(lhs, rhs, mapper)
    return cat_list

  get_catetory_regex_test_pairs: () ->
    test_list = []
    for id, category_object of @category_map
      try
        test_list.push([id, new RegExp(category_object.regex), category_object.ordering])
      catch error
        alert(error)
    test_list.sort((lhs, rhs) -> lhs[2] - rhs[2])
    return test_list

  # return a list of data tuples - (date, acc_balance_1, acc_balance_2...)
  get_merged_transaction_datapoints: () ->
    account_ids = @get_account_ids()
    factory = () ->
      o = {}
      for i in account_ids
        o[i] = null
      return o
    date_to_datum_map = {}
    # update the date dictionary with the latest balance for each day for each account
    for id in account_ids
      transactions = @get_transaction_list(id)
      for transaction in transactions
        date = transaction.date_cleared
        if date
          obj = wsrc.utils.get_or_add_property(date_to_datum_map, date, factory)
          obj[id] = transaction.balance
          obj.date = date
    # convert dicionary to a date-sorted list:
    list = (obj for date, obj of date_to_datum_map)
    list.sort (lhs, rhs) -> wsrc.utils.lexical_sorter(lhs, rhs, (x) -> x.date)
    # backfill blank values in all accounts:
    last_values = {}
    for id in account_ids
        last_values[id] = null
    for item in list
      for id in account_ids
        val = item[id]
        if val
          last_values[id] = val
        else
          item[id] = last_values[id]
    return list
        
  @set_balances = (transactions) ->
    balance = 0
    for transaction in transactions
      unless transaction.date_cleared
        continue
      balance += transaction.amount
      transaction.balance = balance

  get_quarter_summaries: (transactions, years, quarter) ->
    result = {}
    for year in years
      if quarter
        month = (quarter-1) * 3
        start_date = new Date(year, month, 1)
        end_date = new Date(year, month+3, 0)
      else
        start_date = new Date(year, 0, 1)
        end_date = new Date(year, 12, 0)
      result[year] = @summarise_transactions(transactions, start_date, end_date, true)
    return result

  summarise_transactions: (transactions, start_date, end_date, use_cleared_date, include_reconciling_categories) ->
    incoming = 0.0
    outgoing = 0.0
    count = 0
    min_date = end_date
    max_date = start_date
    category_totals = {}
    get_category = (cat_id) ->
      return wsrc.utils.get_or_add_property(category_totals, cat_id, () ->
        {count: 0, incoming: 0, outgoing: 0, net_total: 0.0}
      )
    for transaction in transactions    
      date = if use_cleared_date then transaction.date_cleared else transaction.date_issued
      unless date
        continue
      unless include_reconciling_categories
        category = @get_category(transaction.category)
        if category.is_reconciling
          continue
      date = wsrc.utils.iso_to_js_date(date)
      if date >= start_date and date <= end_date
        if date > max_date
          max_date = date
        if date < min_date
          min_date = date
        if transaction.category.length == 0
          transaction.category = null
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
      net_total: incoming + outgoing 
      count: count
      category_totals: category_totals
      max_date: max_date
      min_date: min_date
    }


################################################################################
# View - JQuery interactions with the html
################################################################################

class WSRC_admin_accounts_view
  
  constructor: (callbacks) ->
    
    @jq_account_transactions_tbody = $('#transactions_tab table.transactions tbody')
    @jq_upload_transactions_tbody = $('#upload_tab table.transactions tbody')
    @jq_summary_tbody = $("#transactions_tab .information-table tbody")
    @jq_summary_tfoot = $("#transactions_tab .information-table tfoot")
    @data_row_selector = 'tr:not(.header)'

    # configure datepickers:
    $("input.datepicker").datepicker().datepicker("option", "dateFormat", "dd/mm/yy")
    today = new Date()
    three_months_back = new Date(today.getYear() + 1900, today.getMonth()-3, today.getDate())
    $("input.datepicker-three-months").datepicker("setDate", three_months_back)
    $("input.datepicker-today").datepicker("setDate", today)

    # configure other UI elements:
    $("#tabs")
      .tabs()
      .removeClass("initiallyHidden")
    $(".radio-buttonset").buttonset()
    $(".button-bar > input[type='button']").button()
    $('.information-set input').attr('readonly', true)    


    @jq_summary_tbody.sortable(
      items: @jq_summary_tbody.children()
      placeholder: "ui-state-highlight"
      update: () ->
        wsrc.utils.apply_alt_class(@jq_summary_tbody.children(), "alt")
    ).disableSelection()

    @swing_dialog = $( "#swing-transaction-dialog" ).dialog(
      autoOpen: false
      height: "auto"
      width: "32em"
      modal: true
      buttons: 
        Create: () =>
          callbacks.create_swing_transaction(@swing_dialog)
        Cancel: () =>
          @swing_dialog.dialog("close")
    )
    @swing_dialog.find("form").on("submit", (event) ->
      event.preventDefault()
      callbacks.create_swing_transaction(@swing_dialog)
    )

  # Open the dialog to swing balances from one category to another
  open_swing_dialog: () -> 
    @swing_dialog.find("select").val("")
    @swing_dialog.find("input[name='amount']").val("0.0")
    @swing_dialog.find("input[name='comment']").val('')
    @swing_dialog.dialog("open")
    return null

  close_swing_dialog: () -> 
    @swing_dialog.dialog("close")
    return null

  # Set options in the combos in the upload transactions screen
  update_category_options: (category_list) ->
    cat_exists = (id) ->
      for [cat_id, cat] in category_list
        if id == cat_id
          return true
      return false
    # add new categories and remove obsolete ones, but leave existing
    # as they may have been manually selected
    jq_selects = @jq_upload_transactions_tbody.find(@data_row_selector).find("select[name='category']")
    jq_selects.each (idx, elt) =>
      jq_select = $(elt)
      options = jq_select.children()      
      options.each (idx, elt) =>
        if idx > 0 # skip blank option
          unless cat_exists(parseInt(elt.value))
            elt.parentElement.removeChild(elt)
      for [cat_id, category] in category_list
        unless jq_select.find("option[value='#{ category.id }']").length > 0
          jq_select.append("<option value='#{ category.id }'>#{ category.description }</option>")
    return null

  set_transaction_summary: (summary) ->
    set_row = (jq_row, cat_summary) ->
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
      
    @jq_summary_tbody.children().each (idx, elt) ->
      jq_row = $(elt)
      cat_id = parseInt(jq_row.data('id'))
      cat_summary = summary.category_totals[cat_id]
      unless cat_summary
        cat_summary = {count: 0, incoming: 0, outgoing: 0, net_total: 0}
      set_row(jq_row, cat_summary)
    set_row(@jq_summary_tfoot.children(), summary)
    return null

  get_account_id: () ->
    parseInt($("#transactions_account_selector").val())
    
  get_transaction_start_date: () ->
    start_date = $("#transactions_start_date_input").datepicker("getDate")
    
  get_transaction_end_date: () ->
    end_date = $("#transactions_end_date_input").datepicker("getDate")
    
  get_transaction_date_type: () ->
    date_type = $("input[name='transactions_date_type']:checked").val()
    
  get_transaction_date_order: () ->
    date_order = $("input[name='transactions_date_ordering']:checked").val()
    
  get_transaction_selected_category_ids: () ->
    categories = []
    @jq_summary_tbody.children().each (idx, elt) ->
      jq_row = $(elt)
      if jq_row.find("td.category input[type='checkbox']").prop('checked')
        categories.push(parseInt(jq_row.data('id')))
    return categories

  add_transaction_rows: (transaction_list, date_type, category_mapper) ->
    @jq_account_transactions_tbody.children().remove()
    for record in transaction_list
      jq_row = @transaction_record_to_row(record, date_type == 'date_cleared', category_mapper)
      @jq_account_transactions_tbody.append(jq_row)
      jq_row.dblclick( (e) =>
        jq_row = $(e.delegateTarget)
        url = "/admin/accounts/transaction/#{ jq_row.data('id') }"
        window.open(url, "editor")
      )
    wsrc.utils.apply_alt_class(@jq_account_transactions_tbody.children(), "alt")
    
    container = @jq_account_transactions_tbody.parents("div.container")
    outer_container1 = container.parent()
    outer_container2 = outer_container1.parent()
    tab_bar = outer_container2.find("ul.ui-tabs-nav")
    fieldset = outer_container1.find("fieldset")
    calc = -30 + outer_container2.height() - tab_bar.outerHeight(true) - fieldset.outerHeight(true) 
    container.css("max-height", "#{ calc }px")
    
  transaction_record_to_row: (record, with_balance, category_mapper) ->
    toBritish = (record, field) ->
      str = record[field]
      unless str
        return ""
      chop = (start, len) -> str.substr(start, len)
      "#{ chop(8,2) }/#{ chop(5,2) }/#{ chop(0,4) }"
    blank = () -> return ""
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
      category_mapper(id).description
    mapping = [
      ['date_issued',  toBritish, blank, str]
      ['date_cleared', toBritish, blank, str]
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
      if data.length > 2
        extra_classes = data[2](record, field)
      sortable = ""
      if data.length > 3
        sortvalue = data[3](record, field)
        sortable = "data-sortvalue='#{ sortvalue }'"
      jq_row.append("<td class='#{ field } #{ extra_classes }' #{ sortable }>#{ value }</td>")
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
      jq_elt = $(elt)
      if jq_elt.find("input[name='duplicate']:checked").length != 1
        transaction = @row_to_transaction_record($(elt))
        date = wsrc.utils.iso_to_js_date(transaction.date_issued)
        if date >= start_date and date <= end_date  
          transactions.push(transaction)
    return transactions    

################################################################################
# Controller - initialize and respond to events
################################################################################

class WSRC_admin_accounts 

  constructor: (@model) ->

    # create the view object:
    callbacks = 
      create_swing_transaction: (dialog) =>
        @create_swing_transaction(dialog.find("form"))
        
    @view = new WSRC_admin_accounts_view(callbacks)

    # configure display of any upload data which was returned in the DOM:
    start_date = new Date(0)
    end_date   = new Date(2099, 1, 1)
    upload_transactions = @view.get_upload_transaction_data(start_date, end_date)
    if upload_transactions.length > 0
      summary = @model.summarise_transactions(upload_transactions, start_date, end_date, false, true)
      $("#upload_start_date_input").datepicker("setDate", summary.min_date)
      $("#upload_end_date_input").datepicker("setDate", summary.max_date)
      @handle_upload_data_changed(summary)
      @apply_category_regexes()

    @handle_categories_updated()    

    $(document).keydown( (e) =>
      if e.ctrlKey and e.which == 66 # 'b' key 
        e.preventDefault()
        @view.open_swing_dialog()
      if e.altKey and e.which == 82 # 'r' key 
        e.preventDefault()
        @reload_account()
    )
    @update_transaction_and_summary_tables()

  handle_categories_updated: () ->
    category_list = @model.get_id_category_pairs()
    @view.update_category_options(category_list)
    return null

  refresh_categories: () ->
    jqmask = $("body")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\Update failed.")
      successCB: (data, status, jq_xhr) =>
        jqmask.unmask()
        @model.set_categories(data)
        @handle_categories_updated()
        @apply_category_regexes()
    jqmask.mask("Refreshing...")
    wsrc.ajax.ajax_bare_helper("/data/accounts/category/", null, opts, "GET")

  apply_category_regexes: () ->
    test_list = @model.get_catetory_regex_test_pairs()
    jq_upload_transactions_tbody = $('#upload_tab table.transactions tbody')
    rows = jq_upload_transactions_tbody.children()
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
    start_date = @view.get_transaction_start_date()
    end_date   = @view.get_transaction_end_date()
    date_type  = @view.get_transaction_date_type()
    categories = @view.get_transaction_selected_category_ids()
    return (transaction) ->
      date = transaction[date_type]
      if date
        date = wsrc.utils.iso_to_js_date(date)
        if date <= end_date and date >= start_date
          if categories.length == 0 or transaction.category in categories
            return true
      return false

  update_transaction_and_summary_tables: () ->
    start_date = @view.get_transaction_start_date()
    end_date   = @view.get_transaction_end_date()
    date_type  = @view.get_transaction_date_type()
    transaction_list = @model.get_transaction_list(@view.get_account_id())
    summary    = @model.summarise_transactions(transaction_list, start_date, end_date, date_type=='date_cleared')
    @view.set_transaction_summary(summary)
    @update_transactions_table(transaction_list)
    return null

  update_transactions_table: (transaction_list) ->
    unless transaction_list?
      transaction_list = @model.get_transaction_list(@view.get_account_id())
    date_type = @view.get_transaction_date_type()   
    date_order = @view.get_transaction_date_order()   
    filter = @get_transaction_filter()
    transactions = (rec for rec in transaction_list when filter(rec))
    if date_type == 'date_issued'
      temp = []
      for rec in transactions
        copy = {}
        for k,v of rec
          if k != 'balance'
            copy[k] = v
        temp.push(copy)
      transactions = temp
      transactions.sort (lhs, rhs) =>
        cmp = wsrc.utils.iso_to_js_date(lhs.date_issued) - wsrc.utils.iso_to_js_date(rhs.date_issued)
        if cmp == 0
          cmp = @model.get_category(lhs.category).ordering - @model.get_category(rhs.category).ordering
        return cmp
    if date_order == 'descending'
      transactions.reverse()
    @view.add_transaction_rows(transactions, date_type, (id) => @model.get_category(id))
    return null        
        
  upload_transactions: () ->
    start_date = $("#upload_start_date_input").datepicker("getDate")
    end_date   = $("#upload_end_date_input").datepicker("getDate")
    data =
      transactions: @view.get_upload_transaction_data(start_date, end_date)
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

  reload_account: (account_id) ->
    unless account_id
      account_id = @view.get_account_id()
    jqmask = $("body")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\Update failed.")
      successCB: (data, status, jq_xhr) =>
        jqmask.unmask()
        @model.set_transaction_list(account_id, data)
        @update_transaction_and_summary_tables()
    jqmask.mask("Reloading...")
    wsrc.ajax.ajax_bare_helper("/data/accounts/account/#{ account_id }/transactions/", null, opts, "GET")

  create_swing_transaction: (form) ->
    account_id = @view.get_account_id()
    from_category = form.find("select[name='from']").val()        
    to_category   = form.find("select[name='from']").val()
    date    = form.find("input[name='date']").datepicker("getDate")
    amount  = form.find("input[name='amount']").val()
    comment = form.find("input[name='comment']").val()
    date = wsrc.utils.js_to_iso_date_str(date)
    data =      
      account: account_id
      transactions: [
        category: from_category
        date_issued: date
        date_cleared: date
        amount: -1.0 * amount
        comment: comment
      ,
        category: to_category
        date_issued: date
        date_cleared: date
        amount: 1.0 * amount
        comment: comment
      ]
    jqmask = $("body")
    opts =
      csrf_token:  $("input[name='csrfmiddlewaretoken']").val()
      failureCB: (xhr, status) -> 
        jqmask.unmask()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\Update failed.")
      successCB: (data, status, jq_xhr) =>
        jqmask.unmask()
        @view.close_swing_dialog()
        @reload_account(account_id)
    wsrc.ajax.ajax_bare_helper("/data/accounts/account/#{ account_id }/transactions/", data, opts, "PUT")
      

  handle_upload_data_changed: (summary) ->
    unless summary
      start_date = $("#upload_start_date_input").datepicker("getDate")
      end_date   = $("#upload_end_date_input").datepicker("getDate")
      transactions = @view.get_upload_transaction_data(start_date, end_date)
      summary = @model.summarise_transactions(transactions, start_date, end_date, false, true)
    $("#upload_transaction_count_input").val(summary.count)
    $("#upload_incoming_input").val(summary.incoming.toFixed(2))
    $("#upload_outgoing_input").val(summary.outgoing.toFixed(2))
    uncategorized = summary.category_totals[null]?.count
    if uncategorized
      $("#upload_uncategorized_count_input").val(uncategorized)
      $("#upload_uncategorized_count_input").parents("div.ui-field-contain").show()
      $("#upload_go_button").attr('disabled', true)
    else
      $("#upload_uncategorized_count_input").parents("div.ui-field-contain").hide()
      $("#upload_go_button").attr('disabled', false)

  draw_quarterlies_chart: (years, quarter) ->
    transactions = @model.get_transaction_list(1)
    results = @model.get_quarter_summaries(transactions, years, quarter)
    data = new google.visualization.DataTable();
    data.addColumn('string', 'Category');
    for year in years
      data.addColumn('number', year)
    for [id, cat] in @model.get_id_category_pairs()
      if cat.is_reconciling
        continue
      row = [cat.description]
      for year in years
        summary = results[year]
        amount = summary.category_totals[id]
        unless amount
          amount = 0.0
        else
          amount = amount.net_total
        row.push(amount)
      data.addRow(row)
    options = 
      chart: 
        title: 'Quarterly Income and Expenditure'
        subtitle: '£'
      width: 800
      height: 500
      bars: 'horizontal'
    chart = new google.charts.Bar($('#chart_pnl_tab .chart_div')[0])
    chart.draw(data, options)
      
    
  draw_balances_chart: (total_mode) ->
    account_ids = @model.get_account_ids()
    list = @model.get_merged_transaction_datapoints()
    data = new google.visualization.DataTable();
    data.addColumn('date', 'Date');
    if total_mode
      data.addColumn('number', 'Total');
    else
      for id in account_ids
        data.addColumn('number', @model.get_account_name(id));
    for item in list
      values = [wsrc.utils.iso_to_js_date(item.date)]
      for id in account_ids
        values.push(item[id])
      if total_mode
        data.addRow([values[0], wsrc.utils.sum(values[1..])])
      else
        data.addRow(values)
    options =
      chart: 
        title: 'Account Balances'
        subtitle: '£'
      width: 1000
      height: 600
    chart = new google.charts.Line($('#chart_balances_tab .chart_div')[0])
    chart.draw(data, options)
    

            
  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: (initial_categories, initial_accounts) ->
    model = new WSRC_admin_accounts_model(initial_categories, initial_accounts)
    @instance = new WSRC_admin_accounts(model)
    wsrc.utils.configure_sortables()
    return null

  @onGraphsReady: () ->
    instance = WSRC_admin_accounts.instance
#    if instance
#      instance.draw_balances_chart(true)
    
admin = wsrc.utils.add_object_if_unset(window.wsrc, "admin")
admin.accounts = WSRC_admin_accounts

