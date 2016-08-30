
utils =
  time_str:  (mins) ->
    pad_zeros = (n) ->
      if n < 10 then "0#{ n }" else n
    return "#{ pad_zeros(Math.floor(mins/60)) }:#{ pad_zeros(mins%60) }"


################################################################################
# Model - contains a local copy of the member databases
################################################################################

class WSRC_court_booking_model
   
  constructor: (day_courts) ->
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


  refresh_table: (earliest, latest, courts, data, resolution) ->
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
          rowspan = slot.duration_mins / resolution
          rowcounts[court] = rowspan-1
          td = $("<td class='slot' rowspan='#{ rowspan }'>#{ @create_booking_cell_content(slot, court) }</td>")
          if slot.id
            td.addClass("booking")
            td.addClass(slot.type)
          else if slot.token
            td.addClass("available")
            td.data("token", slot.token)
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

################################################################################
# Controller - initialize and respond to events
################################################################################


class WSRC_court_booking

  constructor: (@model, date, @server_base_url) ->
    date = wsrc.utils.iso_to_js_date(date)
    @view = new WSRC_court_booking_view()
    options =
      dateFormat: "D, d M yy"
      showOtherMonths: true
      selectOtherMonths: true
      onSelect: (text, obj) =>
        @handle_date_selected(obj)
    datepicker = $("#booking_datepicker_container input").datepicker(options)
    datepicker.datepicker("setDate", date)
    # jquery-ui appends this to the body, but we need it appended to
    # the page wrapper for the overlays and CSS to work properly:
    widget = datepicker.datepicker("widget")
    widget.hide().detach()
    widget.appendTo("#page_wrapper")
    # ensure that clicking anywhere on the input or icon brings up the datepicker:
    $("#booking_datepicker_container").on("click", () ->
      datepicker.datepicker("show") 
    )
    @update_view()

  update_view: () ->
    @view.refresh_table(@model.earliest, @model.latest, @model.courts, @model.day_courts, 15)

  handle_date_selected: (picker) ->
    date = new Date(picker.selectedYear, picker.selectedMonth, picker.selectedDay)
    today_str = wsrc.utils.js_to_iso_date_str(date)
    date.setDate(date.getDate() + 1)
    tomorrow_str = wsrc.utils.js_to_iso_date_str(date)
    url = @server_base_url + "/api/entries.php?start_date=#{ today_str }&end_date=#{ tomorrow_str }&with_tokens=1"
    opts =
      successCB: (data) =>
        @model.refresh(data[today_str])
        @update_view()
      failureCB: (xhr, status) -> 
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to fetch court bookings.")
    wsrc.ajax.GET(url, opts)
    
  @onReady: (day_courts, date, url) ->
    model = new WSRC_court_booking_model(day_courts[date])
    @instance = new WSRC_court_booking(model, date, url)

window.wsrc.court_booking = WSRC_court_booking
