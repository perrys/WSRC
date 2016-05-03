
class WSRC_kiosk_background_view

  constructor: (document) ->
    @root = document

class WSRC_kiosk_background

  constructor: (@app_window) ->
    @wsrc_url = "http://localhost:8000"
    document = @app_window.contentWindow.document
    @view = new WSRC_kiosk_background_view(document)
    handler = (event) => @handle_message_received(event)
    window.addEventListener("message", handler, false)
    chrome.storage.onChanged.addListener (changes, areaName) =>
      if areaName == "local"
        @message_to_app("log", "[bg] detected settings change, attempting login")
        @attempt_login()
      
    @handshake_recieved = false
    poll_handshake = (timeout) =>
      console.log("poll_handshake called")
      unless @handshake_received
        @message_to_app("handshake")
        window.setTimeout(poll_handshake, 2*timeout)
        return null
    poll_handshake(200)

  message_to_app: () ->
    args = $.fn.toArray.call(arguments)
    @app_window.contentWindow.postMessage(args, "*")

  attempt_login: () ->
    chrome.storage.local.get("wsrc_credentials", (data) =>
      credentials = data.wsrc_credentials
      unless credentials?.username and credentials?.password
        @message_to_app("log", "[bg] unable to login, please provide login credentials")
        @message_to_app("show_panels")
        return
      @message_to_app("log", "[bg] attempting login with username: #{ credentials.username }")
      settings =
        url: "#{ @wsrc_url }/data/auth/"
        type: "POST"
        headers:
          "X-CSRFToken": @csrf_token 
        data: credentials
        success: (data, status_txt, jqXHR) =>
          console.log(jqXHR)
          if jqXHR.status == 200
            @csrf_token = data.csrf_token
            @message_to_app("log", "[bg] login successful, username: #{ data.username }")
            @message_to_app("load_webviews")
          else
            @message_to_app("log", "[bg] login failed, please check credentials")
        error: (jqXHR, status_txt, error) =>
            @message_to_app("log", "[bg] login failed (#{ jqXHR.status } #{ jqXHR.statusText }), please check credentials")
      $.ajax(settings)
    )
  check_auth: () ->
    settings =
      url: "#{ @wsrc_url }/data/auth/"
      type: "GET"
      contentType: "application/json"
      success: (data) =>
        @csrf_token = data.csrf_token
        if data.username
          @message_to_app("log", "[bg] logged in, username: #{ data.username }")
          @message_to_app("load_webviews")
        else
          @attempt_login()
      error: (jqXHR, status_txt, error) =>
        console.log(jqXHR)
        console.log(error)
    $.ajax(settings)

  handle_message_received: (event) ->
    console.log("background window received message:  #{ event.data }, from: #{ event.origin }")
    if event.data[0] == "handshake"
      @handshake_received = true
      @message_to_app("log", "[bg] handshake complete")
      @check_auth()

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


