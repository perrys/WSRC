
utils =

        
  time_str:  (mins) ->
    pad_zeros = (n) ->
      if n < 10 then "0#{ n }" else n
    return "#{ pad_zeros(Math.floor(mins/60)) }:#{ pad_zeros(mins%60) }"

  duration_str:  (mins) ->
    hours = Math.floor(mins/60)
    mins  = mins % 60
    result = ""
    if hours > 0
      result += "#{ hours } hour#{ wsrc.utils.plural(hours) } "
    if mins > 0
      result += "#{ mins } min#{ wsrc.utils.plural(mins) } "
    return result

  TYPE_MAP:
    E: "Club"
    I: "Member"
    


################################################################################
# Model - contains a local copy of the member databases
################################################################################

class WSRC_court_booking_model
   
  constructor: (day_courts, @date) ->
    @refresh(day_courts)

  refresh: (day_courts) ->
    courts = (wsrc.utils.to_int(court) for court, slots of day_courts)
    courts.sort()

    maxer = (result, slot) -> Math.max(result, slot.start_mins + slot.duration_mins)
    miner = (result, slot) -> Math.min(result, slot.start_mins)
      
    earliest = 24 * 60
    latest = 0
    for court, slots of day_courts
      earliest = wsrc.utils.reduce_object(slots, miner, earliest)
      latest   = wsrc.utils.reduce_object(slots, maxer, latest)

    @courts      = courts
    @earliest    = earliest
    @latest      = latest
    @day_courts  = day_courts
    

################################################################################
# View - JQuery interactions with the html
################################################################################

class WSRC_court_booking_view

  create_booking_cell_content: (slot, court) ->
    """
      <div class='slot_time'>#{ slot.start_time }&mdash;#{ utils.time_str(slot.start_mins + slot.duration_mins) }<br><span class='court'>Court #{ court }</span></div>
      
      #{ if slot.id then slot.name else if slot.token then '<span class="available">(available)</span>' else '' }
      """


  refresh_table: (earliest, latest, courts, data, resolution, today_current_mins) ->
    table = $(".booking_day")
    header_row = table.find("thead tr")
    header_row.find("th").remove()
    for court in courts
      header_row.append("<th>Court #{ court }</th>")
    body = table.find("tbody")
    body.empty()
    row_mins = earliest
    rowcounts = {}
    last_cells = {}
    last_cell = null
    while row_mins < latest
      row_time = utils.time_str(row_mins)
      row = $("<tr></tr>")
      row.append("<th><div>#{ if (row_mins % 60) == 0 then row_time else "" }</div></th>")
      for court in courts
        slot = data[court][row_time]
        last_td = null
        if slot
          if rowcounts[court] # should not happen - inconsistent data provided            
            continue
          rowspan = slot.duration_mins / resolution
          rowcounts[court] = rowspan-1
          td = $("<td class='slot' rowspan='#{ rowspan }'>#{ @create_booking_cell_content(slot, court) }</td>")
          if today_current_mins
            td.addClass("today")
            if row_mins + slot.duration_mins < today_current_mins
              td.addClass("expired")
          if slot.id
            td.addClass("booking")
            td.addClass(slot.type)
            td.data("id", slot.id)
            td.data("name", slot.name)
            td.data("court", court)
            td.data("start_mins", row_mins)
            td.data("duration_mins", slot.duration_mins)
            td.data("type", slot.type)
            td.data("description", slot.description)
            td.data("created_by", slot.created_by)
            td.data("timestamp", slot.timestamp)
          else if slot.token
            td.addClass("available")
            td.data("token", slot.token)
            td.data("court", court)
            td.data("start_mins", row_mins)
            td.data("duration_mins", slot.duration_mins)
            td.data("type", "I")
          else
            td.addClass("unavailable")
          row.append(td)
          last_cell = last_cells[court] = td
        else
          if rowcounts[court]
            rowcounts[court] -= 1
          else
            row.append("<td></td>")
      body.append(row)
      row_mins += resolution
    for court, cell of last_cells
      cell.addClass("column-last")
    last_cell.addClass("last")

  show_popup: (id, fetcher, edit_mode, update_button_text) ->
    popup = $('#booking_tooltip')
    update_button = popup.find('button.update')
    update_button.text(update_button_text)
    is_edit_mode = update_button.hasClass("togglable")
    if edit_mode != is_edit_mode
      wsrc.utils.toggle(popup)
    popup.find("input[name='id']").val(id)
    popup.find("td:last-child").each (idx, elt) ->
      input = $(elt).find(":input")
      field = input.attr("name")
      val = fetcher(field)
      input.val(val)
      display_val = fetcher(field, true)
      $(elt).find("span").html(display_val)
    popup.popup("open")
    popup.find("select").selectmenu("refresh", true)

  hide_popup: () ->
    popup = $('#booking_tooltip')
    popup.popup("close")
        


################################################################################
# Controller - initialize and respond to events
################################################################################


class WSRC_court_booking

  constructor: (@model, @server_base_url) ->
    @view = new WSRC_court_booking_view()
    @use_proxy = false
    options =
      dateFormat: "D, d M yy"
      showOtherMonths: true
      selectOtherMonths: true
      onSelect: (text, obj) =>
        @handle_date_selected(obj)
    datepicker = $("#booking_datepicker_container input.date-input").datepicker(options)
    datepicker.datepicker("setDate", @model.date)
    # jquery-ui appends this to the body, but we need it appended to
    # the page wrapper for the overlays and CSS to work properly:
    widget = datepicker.datepicker("widget")
    widget.hide().detach()
    widget.appendTo("#page_wrapper")
    # ensure that clicking anywhere on the input or icon brings up the datepicker:
    $("#booking_datepicker_container div.ui-input-text").on("click", () ->
      datepicker.datepicker("show") 
    )
    $("#booking_datepicker_container a.previous").on("click", () =>
      @load_for_date(@model.date, -1)
    )
    $("#booking_datepicker_container a.refresh").on("click", () =>
      @load_for_date(@model.date, 0)
    )
    $("#booking_datepicker_container a.next").on("click", () =>
      @load_for_date(@model.date, 1)
    )
    $("table.booking_day").on("swipeleft", () =>
      @load_for_date(@model.date, 1)
    )
    $("table.booking_day").on("swiperight", () =>
      @load_for_date(@model.date, -1)
    )
    $("#booking_tooltip button.delete").on("click", (evt) =>
      id = wsrc.utils.to_int($("#booking_tooltip input[name='id']").val())
      if confirm('Are you sure you want to delete this entry?\n')
        $("#booking_tooltip").popup("close")
        @delete_entry(id)
    )
    $("#booking_tooltip button.edit").on("click", (evt) =>
      popup = $("#booking_tooltip")
      wsrc.utils.toggle(popup)
    )
    $("#booking_tooltip button.update").on("click", (evt) =>
      popup_form = $("#booking_tooltip form")
      fetcher = (field) ->
        return popup_form.find(":input[name='#{ field }']").val()
      @create_or_update_entry(fetcher)
    )
    qp = (val) ->
      vals = val.split("=")
      k = vals.shift()
      return [k, vals.join("=")]
    params = (qp(v) for v in location.search.substr(1).split("&"))
    @params = wsrc.utils.list_of_tuples_to_map(params)
      
    @update_view()

  update_view: () ->
    datepicker = $("#booking_datepicker_container input")
    datepicker.datepicker("setDate", @model.date)
    today_current_mins = null
    right_now = new Date() # note - relies on local clock being accurate and in the correct timezone
    if wsrc.utils.is_same_date(@model.date, right_now)
      today_current_mins = right_now.getHours() * 60 + right_now.getMinutes()
    @view.refresh_table(@model.earliest, @model.latest, @model.courts, @model.day_courts, 15, today_current_mins)
    $("td.booking").on("click", (evt) =>
      source_cell = $(evt.target)
      fetcher = (field, for_display) ->
        val = source_cell.data(field)
        if for_display
          if field == "type"
            return utils.TYPE_MAP[val]
          if field == "start_mins"
            return utils.time_str(val)
          if field == "duration_mins"
            return utils.duration_str(val)
        return val
      @view.show_popup(source_cell.data("id"), fetcher, false, "Update")
    )
    $("td.available").on("click", (evt) =>
      source_cell = $(evt.target)
      unless source_cell.hasClass("slot")
        source_cell = source_cell.parents("td.slot")
      fetcher = (field) ->
        if field == "name"
          return window.WSRC_booking_user_name
        source_cell.data(field)
      @view.show_popup('', fetcher, true, "Create")
    )

  create_or_update_entry: (source) ->
    data =
      user_id: window.WSRC_booking_user_id
      user_token: window.WSRC_booking_user_auth_token
      date: wsrc.utils.js_to_iso_date_str(@model.date)
    for field in ["name", "description", "type"]
      data[field] = source(field)
    id = source("id") # updating an existing entry
    if id
      data.id = id
    else
      for field in ["start_mins", "duration_mins", "court", "token"]
        data[field] = source(field)
      
    using_proxy = @use_proxy
    url = @server_base_url + "/api/entries.php"
    opts =
      content_type: "text/plain"
      successCB: (data) =>
        @view.hide_popup()
        @load_for_date(@model.date)
      failureCB: (xhr, status) =>
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to update booking.")

    if id # updating, need to send a PATCH
      url += "?id=#{ id }"
      data.url = url
      opts.csrf_token = $("input[name='csrfmiddlewaretoken']").val()
      wsrc.ajax.PATCH("/court_booking/proxy/", data, opts) # PATCH must be sent via the proxy
    else # new entry - this is a POST
      if using_proxy
        opts.csrf_token = $("input[name='csrfmiddlewaretoken']").val()
        data.url = url
        wsrc.ajax.POST("/court_booking/proxy/", data, opts)
      else
        opts.failureCB = (xhr, status) =>
          if not using_proxy
            if @params.debug
              alert("Failed to load directly from booking system, falling back to proxy")
            @use_proxy = true
            @create_or_update_entry(source)
          else
            alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to make court booking.")
        wsrc.ajax.POST(url, data, opts)
  
  delete_entry: (id) ->
    payload =
      user_id: window.WSRC_booking_user_id
      user_token: window.WSRC_booking_user_auth_token
      url: @server_base_url + "/api/entries.php?id=#{ id }"
      method: "DELETE"
    opts =
      csrf_token: $("input[name='csrfmiddlewaretoken']").val()
      successCB: (data) =>
        @view.hide_popup()
        @load_for_date(@model.date)
      failureCB: (xhr, status) =>
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to delete entry #{ id }.")
    # cannot send DELETE cross-origin, always need to go via proxy:
    wsrc.ajax.POST("/court_booking/proxy/", payload, opts)

  load_for_date: (aDate, offset) ->
    d1 = new Date(aDate.getTime())
    if offset
      d1.setDate(d1.getDate()+offset)
    today_str = wsrc.utils.js_to_iso_date_str(d1)
    d2 = new Date(d1.getTime())
    d2.setDate(d2.getDate() + 1)
    tomorrow_str = wsrc.utils.js_to_iso_date_str(d2)
    url = @server_base_url + "/api/entries.php?start_date=#{ today_str }&end_date=#{ tomorrow_str }&with_tokens=1"
    using_proxy = @use_proxy
    opts =
      successCB: (data, status, jqxhr) =>
        @model.date = d1
        @model.refresh(data[today_str])
        @update_view()
      failureCB: (xhr, status) =>
        if xhr.status == 0 and not using_proxy
          if @params.debug
            alert("Failed to load directly from booking system, falling back to proxy")
          @use_proxy = true
          @load_for_date(aDate, offset)
        else
          alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to fetch court bookings.")
    if using_proxy
      opts.csrf_token = $("input[name='csrfmiddlewaretoken']").val()
      payload =
        url: url
        method: "GET"
      wsrc.ajax.POST("/court_booking/proxy/", payload, opts)
    else
      wsrc.ajax.GET(url, opts) 

  handle_date_selected: (picker) ->
    date = new Date(picker.selectedYear, picker.selectedMonth, picker.selectedDay)
    @load_for_date(date)
    
  @onReady: (day_courts, date_str, url) ->
    date = wsrc.utils.iso_to_js_date(date_str)
    model = new WSRC_court_booking_model(day_courts[date_str], date)
    @instance = new WSRC_court_booking(model, url)

window.wsrc.court_booking = WSRC_court_booking
