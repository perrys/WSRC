utils =
        
  duration_str:  (mins) ->
    hours = Math.floor(mins/60)
    mins  = mins % 60
    result = ""
    if hours > 0
      result += "#{ hours } hour#{ wsrc.utils.plural(hours) } "
    if mins > 0
      result += "#{ mins } minute#{ wsrc.utils.plural(mins) } "
    return result

class WSRC_court_booking

  constructor: (@base_path) ->
    datepicker_options =
      dateFormat: "D, d M yy"
      firstDay: 1
      showOtherMonths: true
      selectOtherMonths: true
      onSelect: (text, obj) =>
        @handle_date_selected(obj)
    datepicker = $("input.date-input").datepicker(datepicker_options).show()
    # jquery-ui appends this to the body, but we need it appended to
    # the page wrapper for the overlays and CSS to work properly:
    widget = datepicker.datepicker("widget")
    widget.hide().detach()
    widget.appendTo("body .container")
    
    $("a.previous").on("click", (evt) => @load_day_table(evt, -1))
    $("a.refresh").on("click", (evt) => @load_day_table(evt))
    $("a.next").on("click", (evt) => @load_day_table(evt, 1))

    $(document).keydown( (e) =>
      if e.altKey and e.which == 82 # 'r' key 
        e.preventDefault()
        @load_day_table(e, 0)
      if e.altKey and e.which == 80 # 'p' key 
        @load_day_table(e, -1)
      if e.altKey and e.which == 78 # 'n' key 
        e.preventDefault(e)
        @load_day_table(e, 1)
    )

  start_load_spinner: () ->
     $(".refresh span").addClass("glyphicon-refresh-animate")
 
  stop_load_spinner: () ->
    $(".refresh span").removeClass("glyphicon-refresh-animate")
 
  fast_load_day: (date) ->
    date_str = wsrc.utils.js_to_iso_date_str(date)
    opts =
      url: @base_path + "/" + date_str + "?table_only=1"
      type: 'GET' 
      success: (data, status, jqxhr) =>
        @stop_load_spinner()
        @update_view(date, data)
      error: (xhr, status) =>
        @stop_load_spinner()
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to fetch court bookings.")
    @start_load_spinner()
    jQuery.ajax(opts)

  update_view: (date, data) ->
    table = $("div#booking-day table")
    table.replaceWith(data)
    $("input.date-input").datepicker("setDate", date);
    if history
      url = @base_path + "/" +  wsrc.utils.js_to_iso_date_str(date)
      history.pushState({}, "", url)

  load_day_table: (evt, offset) ->
    if evt
      evt.stopPropagation()
      evt.preventDefault()
    table = $("div#booking-day table")    
    d1 = new Date(table.data("date"))
    if offset
      d1.setDate(d1.getDate()+offset)
    @fast_load_day(d1)
    return undefined

  handle_booking_request: (e, elt) ->
    e.stopPropagation()
    e.preventDefault()
    td = $(elt)
    table = td.parents("table")
    court = td.data("court")
    start_time = td.data("start_time")
    duration = td.data("duration_mins")
    msg = "Would you like to make the following booking?\n\n#{ table.data('date_str') }\n#{ start_time } for #{ utils.duration_str(duration) }\nCourt #{ court }"
    if confirm(msg)
      form = $("form#court_booking_form")
      set = (k,v) -> form.find("input[name='#{ k }']").val(v)
      set("court", court)
      set("start_time", start_time)
      set("date", table.data("date"))
      set("token", td.data("token"))
      set("duration", "#{ duration } mins")
      opts =
        url: form.attr("action")
        type: 'POST'
        data: form.serialize()
        success: (data, status, jqxhr) =>
          @stop_load_spinner()
          @load_day_table(null, 0)
        error: (xhr, status) =>
          @stop_load_spinner()
          form.submit()
      @start_load_spinner()
      jQuery.ajax(opts)
    return false
    
  handle_date_selected: (picker) ->
    date = new Date(picker.selectedYear, picker.selectedMonth, picker.selectedDay)
    @fast_load_day(date)
    
  @onReady: (base_path) ->
    @instance = new WSRC_court_booking(base_path)
        

window.wsrc.court_booking = WSRC_court_booking
