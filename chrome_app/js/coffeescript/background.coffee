
bytes_to_blob = (byteCharacters, contentType='', sliceSize=512) ->

  byteArrays = [];
  offset = 0

  while offset < byteCharacters.length
    slice = byteCharacters.slice(offset, offset + sliceSize)
    offset += sliceSize

    byteNumbers = new Array(slice.length)
    i = 0
    while i < slice.length
      byteNumbers[i] = slice.charCodeAt(i)
      ++i

    byteArrays.push(new Uint8Array(byteNumbers));

  return new Blob(byteArrays, {type: contentType})

  
class WSRC_kiosk_background_view

  constructor: (document) ->
    @root = document

class WSRC_kiosk_background

  constructor: (@app_window) ->
    @settings_defaults =
      wsrc_credentials:
        server: "www.wokingsquashclub.org"
        username: "kiosk_user"
      kiosk_settings:
        booking_fetch_period: 5
        events_fetch_period: 30
        events_refresh_period: 45
        webview_timeout: 2
        virtual_keyboard: "on"
            
    @club_event_check_period_minutes = 60
    document = @app_window.contentWindow.document
    @view = new WSRC_kiosk_background_view(document)
    handler = (event) => @handle_message_received(event)
    window.addEventListener("message", handler, false)
    chrome.storage.onChanged.addListener (changes, areaName) =>
      if areaName == "local"
        @handle_alarm_load_court_bookings()
        @handle_alarm_load_club_events()
        @message_to_app("log", "[bg] detected settings change, checking login credentials")
        @check_auth()
      
    @handshake_recieved = false
    poll_handshake = (timeout) =>
      unless @handshake_received
        @message_to_app("handshake")
        window.setTimeout(poll_handshake, 2*timeout)
        return null
    poll_handshake(200)

    @handle_alarm_load_court_bookings()
    @handle_alarm_load_club_events()
    booking_alarm = "load_court_bookings"
    chrome.alarms.onAlarm.addListener (alarm) =>
      method = @["handle_alarm_#{ alarm.name }"]
      if method
        method.apply(this)
    @get_settings (settings) =>
      chrome.alarms.create("load_court_bookings", {periodInMinutes: settings.kiosk_settings.booking_fetch_period})
      chrome.alarms.create("load_club_events",    {periodInMinutes: settings.kiosk_settings.events_fetch_period})
    @handle_alarm_get_system_status()
    chrome.alarms.create("get_system_status", {periodInMinutes: 1})

  message_to_app: () ->
    args = $.fn.toArray.call(arguments)
    @app_window.contentWindow.postMessage(args, "*")

  handle_alarm_load_court_bookings: () ->
    @get_settings (stored_data) =>
      credentials = stored_data.wsrc_credentials
      kiosk_settings = stored_data.kiosk_settings
      today = wsrc.utils.js_to_iso_date_str(new Date())
      settings =
        url: "http://#{ credentials.server }/data/bookings?date=#{ today }"
        type: "GET"
        complete: (jqXHR, status_txt) =>
          if jqXHR.status == 200
            @message_to_app("court_bookings_update", jqXHR.responseJSON, kiosk_settings)
          else
            @message_to_app("log", "[bg] error fetching court bookings (#{ jqXHR.status } #{ jqXHR.statusText }) - #{ status }")
      $.ajax(settings)
  
  handle_alarm_load_club_events: () ->
    @get_settings (stored_data) =>
      credentials = stored_data.wsrc_credentials
      kiosk_settings = stored_data.kiosk_settings
      settings =
        url: "http://#{ credentials.server }/data/club_events"
        type: "GET"
        complete: (jqXHR, status_txt) =>
          if jqXHR.status == 200
            events = jqXHR.responseJSON
            for event in events
              @preprocess_club_event(event)
            @message_to_app("club_events_update", events, kiosk_settings)
          else
            @message_to_app("log", "[bg] error fetching club events (#{ jqXHR.status } #{ jqXHR.statusText }) - #{ status }")
      $.ajax(settings)

  handle_alarm_get_system_status: () ->
    calc_pcts = (current, previous, i) ->
      current = current.processors[i].usage
      previous = previous.processors[i].usage
      total  = 1.0 * (current.total - previous.total)
      idle   = 1.0 * (current.idle - previous.idle)
      user   = 1.0 * (current.user - previous.user)
      kernel = 1.0 * (current.kernel - previous.kernel)
      result =
        idle:   100 * idle/total
        user:   100 * user/total
        kernel: 100 * kernel/total
    chrome.system.cpu.getInfo (cpu_info) =>
      if @previous_cpu_info
        ncpus = cpu_info.numOfProcessors
        percentages = (calc_pcts(cpu_info, @previous_cpu_info, i) for i in [0...ncpus])
        @message_to_app("cpu_usage", percentages)
      @previous_cpu_info = cpu_info
    chrome.system.network.getNetworkInterfaces (networks) =>
        @message_to_app("networks", networks)
        names = {}
        for network in networks
          names[network.name] = null
        names = (name for name, dummy of names)
        handle_wireless_info = (info) =>
          if info
            @message_to_app("wireless_info", info)
        @fetch_wireless(names, handle_wireless_info)
    
  preprocess_club_event: (data) =>
    if data.picture
      binary_data = atob(data.picture.data)
      if binary_data.length != data.picture.size
        console.log("ERROR: decoded picture #{ data.picture.name } size mismatch - got #{ binary_data.length }, expected #{ data.picture.size }")
      else
        ext = data.picture.name.split(".").slice(-1)[0]
        type = "image/#{ ext }"
        blob = bytes_to_blob(binary_data, type)
        data.picture.url = URL.createObjectURL(blob)
    return data

  get_settings: (callback) =>
    chrome.storage.local.get (settings) =>
      merged = {}
      $.extend(true, merged, @settings_defaults, settings)
      callback.call(_this, merged)
    

  attempt_login: () ->
    @get_settings (stored_data) =>
      credentials = stored_data.wsrc_credentials
      unless credentials?.username and credentials?.password
        @message_to_app("log", "[bg] unable to login, please provide login credentials")
        @message_to_app("show_panels")
        return
      @message_to_app("log", "[bg] attempting login with username: #{ credentials.username }")
      settings =
        url: "http://#{ credentials.server }/data/auth/"
        type: "POST"
        headers:
          "X-CSRFToken": @csrf_token 
        data: credentials
        complete: (jqXHR) =>
          data = jqXHR.responseJSON
          if jqXHR.status == 200
            @csrf_token = data.csrf_token
            @message_to_app("log", "[bg] login successful, username: #{ data.username }")
            @message_to_app("login_webviews", credentials)
          else
            @message_to_app("log", "[bg] login failed (#{ jqXHR.status } #{ jqXHR.statusText }), response: #{ jqXHR.responseText }, please check credentials")
      $.ajax(settings)
      
  check_auth: () ->
    @get_settings (stored_data) =>
      @message_to_app("settings_update", stored_data)
      credentials = stored_data.wsrc_credentials
      settings =
        url: "http://#{ credentials.server }/data/auth/"
        type: "GET"
        contentType: "application/json"
        success: (data) =>
          @csrf_token = data.csrf_token
          if data.username
            if data.username == credentials.username
              @message_to_app("log", "[bg] logged in, username: #{ data.username }")
              @message_to_app("login_webviews", credentials)
            else
              @message_to_app("log", "[bg] incorrect username: #{ data.username }")
              @attempt_login()
          else
            @attempt_login()
        error: (jqXHR, status_txt, error) =>
          console.log(jqXHR)
          console.log(error)
      $.ajax(settings)
  
  handle_message_received: (event) ->
    if event.data[0] == "handshake"
      @handshake_received = true
      @message_to_app("log", "[bg] handshake complete")
      @check_auth()
      @get_settings (stored_data) =>
        @message_to_app("settings_update", stored_data)

  fetch_wireless: (interface_names, handler) ->
    msg =
      interfaces: interface_names
    chrome.runtime.sendNativeMessage("org.wokingsquashclub.chrome_app.wireless", msg, handler)

  @onReady: (app_window) ->
    app_window.contentWindow.addEventListener("load", () =>
      console.log("kiosk window loaded...")
      window.wsrc_kiosk.instance = new WSRC_kiosk_background(app_window)
    )

window.wsrc_kiosk = WSRC_kiosk_background
  
chrome.app.runtime.onLaunched.addListener () ->
  options = 
    'state': 'fullscreen'
  chrome.app.window.create('window.html', options, WSRC_kiosk_background.onReady)


