
utils = 
  to_12h_time_str: (dt, with_am_pm) ->
    hour = dt.getHours()
    ampm = ""
    if with_am_pm
      ampm = if hour < 12 then " AM" else " PM"
    if hour > 12
      hour -= 12
    else if hour == 0
      hour = 12
    min = dt.getMinutes()
    if min < 10
      min = "0#{ min }"
    return "#{ hour }:#{ min }#{ ampm }"
    
  toint: (s) ->
    parseInt(s, 10)
    
  parse_date: (dt_str) ->
    y = this.toint(dt_str.substr(0,4))
    m = this.toint(dt_str.substr(5,2))
    d = this.toint(dt_str.substr(8,2))
    ho = this.toint(dt_str.substr(11,2))
    mi = this.toint(dt_str.substr(14,2))
    se = this.toint(dt_str.substr(17,4))
    offset_mi = 0
    if dt_str.length > 19
      offset_ho = this.toint(dt_str.substr(20,2))
      offset_mi = this.toint(dt_str.substr(23,2))
      offset_mi += offset_ho * 60
      if dt_str.substr(19,1) != "-"
        offset_mi = offset_mi * -1
    date = new Date(Date.UTC(y, m-1, d, ho, mi + offset_mi, se)) 
    return date

  
class WSRC_kiosk_view

  constructor: () ->
    @log_id = 0
    $("#settings_panel").panel("open")
    $("input").vkeyboard()
    @populate_settings_form()
    

  log: (message) ->
    now = new Date()
    date = wsrc.utils.js_to_iso_date_str(now)
    time = now.toTimeString().substr(0,8)
    message = "#{ date } #{ time } #{ message }"
    $("#log_console").append("<div id='log_#{ @log_id }'>#{ message }</div>")
    return @log_id++

  show_panels: () ->
    $("#settings_panel").panel("open")

  hide_panels: () ->
    $("#settings_panel").panel("close")
        
  update_clock: (val) ->
    $('div.clock').html(val)

  update_courts: (data) ->
    court_map = {}
    factory = () ->
      return []
    for booking in data
      bookings = wsrc.utils.get_or_add_property(court_map, booking.court, factory)
      bookings.push(booking)
      booking.start_time_js = utils.parse_date(booking.start_time)
      booking.end_time_js   = utils.parse_date(booking.end_time)

    now_courts = {}
    next_courts = {}
    now = new Date()
#    now = new Date(2016, 3, 25, 19, 23)
    for court, bookings of court_map
      wsrc.utils.lexical_sort(bookings, "start_time")
      now_court_found = false
      next_court_found = false
      for booking in bookings
        if booking.start_time_js <= now and  booking.end_time_js > now
          now_courts[court] = booking
          now_court_found = true
        else if booking.start_time_js > now and not next_court_found
          next_courts[court] = booking
          next_court_found = true
    display_court = (type, court, booking) ->
      jq_row = $("#court#{ court }_#{ type }")
      jq_row.find("td.time").html("#{ utils.to_12h_time_str(booking.start_time_js) }&mdash;#{ utils.to_12h_time_str(booking.end_time_js,true) }")
      jq_row.find("td.description").html(if booking.name then booking.name else "-")
    for court, booking of now_courts
      display_court("now", court, booking)
    for court, booking of next_courts
      display_court("next", court, booking)

  get_settings: () ->
    data = {}
    $("#settings_panel fieldset").each (idx, elt) ->
      fieldset = $(this)
      group_data = data[fieldset.data("group")] = {}
      fieldset.find(":input").each () ->
        input = $(this)
        group_data[input.attr("name")] = input.val()
    return data

  populate_settings_form: () ->
    $("#settings_panel fieldset").each (idx, elt) ->
      fieldset = $(this)
      group_key = fieldset.data("group")
      chrome.storage.local.get(group_key, (data) =>
        for key, val of data[group_key]
          fieldset.find(":input[name='#{ key }']").val(val)
      )

  update_club_event: (event) ->
    panel = $("#notifications")
    date = ""
    if event?.display_date
      jsdate = wsrc.utils.iso_to_js_date(event.display_date)
      date += wsrc.utils.js_to_readable_date_str(jsdate)
    if event?.display_time
      jsdate = utils.parse_date("2000-01-01 #{ event.display_time }")
      date += " " + utils.to_12h_time_str(jsdate, true)
    options =
      duration: 2 * 1000
      complete: () ->
        if event
          panel.find(".heading").text(event.title)
          panel.find(".date").text(date)
          panel.find(".ui-body").html(event.markup)
          panel.fadeIn(3 * 1000)
    panel.fadeOut(options)
    
class WSRC_kiosk

  constructor: () ->
    @wsrc_host = "localhost:8000"
    @logo_click_count = 0
    @club_event_idx = 0
    @view = new WSRC_kiosk_view()
    $("#settings_apply_btn").click (evt) =>
      @handle_update_settings(evt);
    $('#yellow_dots_img').click (evt) =>
      @handle_logo_click(evt)
    
    @view.log("waiting for handshake")
    handler = (event) => @handle_message_received(event)
    window.addEventListener("message", handler, false)

    window.setInterval ( => @update_clock()), 500


  handle_message_received: (event) ->
    method = "handle_message_" + event.data[0]
    args = event.data[1..]
    args.unshift(event)
    @[method].apply(this, args)

  handle_message_handshake: (event) ->
    @view.log("received handshake from #{ event.origin }")
    @background_window = event.source
    @background_window.postMessage(["handshake"], "*")

  handle_message_log: (event, message) ->
    @view.log(message)

  handle_message_show_panels: (event) ->
    @view.show_panels()

  handle_message_court_bookings_update: (event, data) ->
    @court_bookings = data
    unless @court_update_started
      updater = () => @view.update_courts(@court_bookings)
      updater()
      window.setInterval updater, 6 * 1000
      @court_update_started = true

  handle_message_club_events_update: (event, data) ->
    @club_events = data
    unless @club_event_update_started
      updater = () =>
        len = @club_events.length
        if len == 0
          event = null
        else
          if @club_event_idx >= len
            @club_event_idx = 0
          event = @club_events[@club_event_idx++]
        @view.update_club_event(event)
        return null
      updater()
      window.setInterval(updater, 45 * 1000)
      @club_event_update_started = true

  handle_message_login_webviews: () ->
    login_webview = $("webview#login_webview")[0]
    rule = 
      name: 'listener_rule'
      matches: ["http://#{ @wsrc_host }/*"]
      js:
        files: ["js/_jquery.js", "js/client_functions.js"]
      run_at: 'document_end'
    login_webview.addContentScripts([rule])
    src = "http://#{ @wsrc_host }/login/"
    @view.log("loading login webview: #{ src }")
    login_webview.addEventListener('contentload', (event) =>
      credentials = @view.get_settings().wsrc_credentials
      login_webview.contentWindow.postMessage(["login", credentials.username, credentials.password], "http://#{ @wsrc_host }")
      return null
    )
    login_webview.src = src
    
  handle_message_load_webviews: () ->
    webviews = $("webview.wsrc-client")
    webviews.each (idx, wv) =>
      @load_webview(wv)
    @view.hide_panels()
                
  handle_update_settings: (event) ->
    data = @view.get_settings()
    chrome.storage.local.set(data, () =>
      if chrome.runtime.lastError
        @view.log("error persisting settings: #{ chrome.runtime.lastError }")
        console.log(chrome.runtime.lastError)
    )

  handle_logo_click: (event) ->
    if @logo_click_count == 0
      @logo_click_count = 1
      cb = () =>
        @logo_click_count = 0
      window.setTimeout(cb, 10*1000)
    else
      @logo_click_count++
      if @logo_click_count >= 10
        @view.show_panels() 
            
  load_webview: (webview) ->
    if webview.src
      return
    src = $(webview).data("src")
    src = "http://#{ @wsrc_host }/#{ src }?no_navigation"    
    rule = 
      name: 'vkeyboard'
      matches: ["http://#{ @wsrc_host }/*"]
      js:
        files: ["js/_jquery.js", "js/_jquery-ui.js", "js/jquery.vkeyboard.js", "js/client_functions.js"]
      css:
        files: ["css/jquery.vkeyboard.css"]
      run_at: 'document_end'
    webview.addContentScripts([rule])
    id = $(webview).parents("div").attr("id")
    @view.log("webview #{ id } loading: #{ src }") 
    webview.src = src

  update_clock: () ->
    now = new Date()
    date_str = wsrc.utils.js_to_readable_date_str(now)
    time_str = now.toLocaleTimeString()
    @view.update_clock(date_str + " " + time_str)    

  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])

  @onReady: () ->
    @instance = new WSRC_kiosk()
      

window.wsrc_kiosk = WSRC_kiosk

$(document).on("ready", () ->
  wsrc_kiosk.onReady()
  
)
