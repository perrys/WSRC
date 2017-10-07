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
      result += "#{ mins } minute#{ wsrc.utils.plural(mins) } "
    return result

class WSRC_court_booking

  constructor: (@base_path) ->
    datepicker_options =
      dateFormat: "D, d M yy"
      showOtherMonths: true
      selectOtherMonths: true
      onSelect: (text, obj) =>
        @handle_date_selected(obj)
    datepicker = $("#booking_datepicker_container input.date-input").datepicker(datepicker_options)
    # jquery-ui appends this to the body, but we need it appended to
    # the page wrapper for the overlays and CSS to work properly:
    widget = datepicker.datepicker("widget")
    widget.hide().detach()
    widget.appendTo("#page_wrapper")
    # ensure that clicking anywhere on the input or icon brings up the datepicker:
    $("#booking_datepicker_container div.ui-input-text").on("click", () ->
      datepicker.datepicker("show") 
    )
    
    $("#booking_datepicker_container a.previous").attr("href", "javascript:wsrc.court_booking.on('load_day_table', -1)")
    $("#booking_datepicker_container a.refresh").attr("href",  "javascript:wsrc.court_booking.on('load_day_table')")
    $("#booking_datepicker_container a.next").attr("href",     "javascript:wsrc.court_booking.on('load_day_table', 1)")
    $("div#booking_day").on("swipeleft", () =>
      @load_day_table(1)
    )
    $("div#booking_day").on("swiperight", () =>
      @load_day_table(-1)
    )
    $(document).keydown( (e) =>
      if e.altKey and e.which == 82 # 'r' key 
        e.preventDefault()
        @load_day_table(0)
      if e.altKey and e.which == 80 # 'p' key 
        e.preventDefault()
        @load_day_table(-1)
      if e.altKey and e.which == 78 # 'n' key 
        e.preventDefault()
        @load_day_table(1)
    )

  fast_load_day: (date) ->
    date_str = wsrc.utils.js_to_iso_date_str(date)
    opts =
      url: @base_path + "/" + date_str + "?table_only=1"
      type: 'GET' 
      success: (data, status, jqxhr) =>
        jQuery.mobile.loading("hide")
        @update_view(date, data)
      error: (xhr, status) =>
        jQuery.mobile.loading("hide")
        alert("ERROR #{ xhr.status }: #{ xhr.statusText }\nResponse: #{ xhr.responseText }\n\nUnable to fetch court bookings.")
    jQuery.mobile.loading("show", 
      text: "Fetching " + date_str
      textVisible: false
      theme: "a"
    )
    jQuery.ajax(opts)

  update_view: (date, data) ->
    table = $("div#booking-day table")
    table.replaceWith(data)
    datepicker = $("#booking_datepicker_container input.date-input")
    datepicker.datepicker("setDate", date)
    $("#booking_footer div.date").text($.datepicker.formatDate("D, d M yy", date))
    if history
      url = @base_path + "/" +  wsrc.utils.js_to_iso_date_str(date)
      history.pushState({}, "", url)

  load_day_table: (offset) ->
    table = $("div#booking-day table")    
    d1 = new Date(table.data("date"))
    if offset
      d1.setDate(d1.getDate()+offset)
    @fast_load_day(d1)

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
      form.submit()
    return false
    
  handle_date_selected: (picker) ->
    date = new Date(picker.selectedYear, picker.selectedMonth, picker.selectedDay)
    @fast_load_day(date)
    
  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: (base_path) ->
    @instance = new WSRC_court_booking(base_path)
        

window.wsrc.court_booking = WSRC_court_booking
