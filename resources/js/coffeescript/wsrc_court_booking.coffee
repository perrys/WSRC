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

  getLocation: ( event ) ->
    winPageX = window.pageXOffset
    winPageY = window.pageYOffset
    x = event.clientX
    y = event.clientY

    if (event.pageY == 0 and Math.floor(y) > Math.floor(event.pageY) or
        event.pageX == 0 and Math.floor(x) > Math.floor(event.pageX))
      # iOS4 clientX/clientY have the value that should have been
      # in pageX/pageY. While pageX/page/ have the value 0
      x = x - winPageX
      y = y - winPageY
    else if (y < (event.pageY - winPageY) || x < (event.pageX - winPageX)) 
      # Some Android browsers have totally bogus values for clientX/Y
      # when scrolling/zooming a page. Detectable since clientX/clientY
      # should never be smaller than pageX/pageY minus page scroll
      x = event.pageX - winPageX;
      y = event.pageY - winPageY;

    return
      x: x
      y: y

class WSRC_court_booking

  constructor: (@base_path, @is_admin_view) ->
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
    $("a.toggle_admin").on("click", (evt) => @handle_toggle_admin(evt, 0))
    $("a.next").on("click", (evt) => @load_day_table(evt, 1))

    # swipe function
    duration_threshold = 1000    
    # Swipe vertical displacement must be less than this.
    v_distance_threshold = 30
    distance_threshold = 50
    @still_moving = false
    @start = null
    @start_time = null
    $("div#booking-day").on("touchstart", (evt) =>
      data = if evt.originalEvent.touches then evt.originalEvent.touches[0] else evt
      @start = utils.getLocation(data)
      @start_time = (new Date()).getTime()
      @still_moving = true;
    )
    $("div#booking-day").on("touchmove", (evt) =>
      if @still_moving
        data = if evt.originalEvent.touches then evt.originalEvent.touches[0] else evt
        location = utils.getLocation(data)
        delta_x = @start.x - location.x
        delta_y = Math.abs(@start.y - location.y)
        duration = (new Date()).getTime() - @start_time
        if duration > duration_threshold or delta_y > v_distance_threshold
          @still_moving = false
        else
          if delta_x > distance_threshold
            @still_moving = false
            @load_day_table(evt, 1)
          else if delta_x < (-1.0 * distance_threshold)
            @still_moving = false
            @load_day_table(evt, -1)
    )

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

  make_base_url: (date, is_admin_view) ->
    date_str = wsrc.utils.js_to_iso_date_str(date)
    admin_prefix = if is_admin_view then "/admin" else ""
    return @base_path + admin_prefix + "/" + date_str

  get_table_date: () ->
    table = $("div#booking-day table")    
    return new Date(table.data("date"))
         
  fast_load_day: (date) ->
    opts =
      url: @make_base_url(date, @is_admin_view) + "?table_only=1"
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
      url = @make_base_url(date, @is_admin_view)
      history.pushState({}, "", url)

  load_day_table: (evt, offset) ->
    if evt
      evt.stopPropagation()
      evt.preventDefault()
    d1 = @get_table_date()
    if offset
      d1.setDate(d1.getDate()+offset)
    @fast_load_day(d1)
    return undefined

  handle_toggle_admin: (e) ->
    e.stopPropagation()
    e.preventDefault()
    date = @get_table_date()
    url = @make_base_url(date, not @is_admin_view)
    document.location = url
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
    
  @onReady: (base_path, is_admin_view) ->
    @instance = new WSRC_court_booking(base_path, is_admin_view)
        

window.wsrc.court_booking = WSRC_court_booking
