

dispatch = (event) ->
  post_message = (args) ->
    event.source.postMessage(args, event.origin)
  post_log_message = (msg) ->
    post_message(["log", "[wv] #{ msg }"])
    
  functions =
  
    get_username: () ->
      return $("input[name='current_username']").val()

    login: (username, password) ->
      csrf_token = $("input[name='csrfmiddlewaretoken']").val()
      origin = document.location.origin
      url = "#{ origin }/data/auth/"
      settings =
        url: url
        type: "POST"
        headers:
          "X-CSRFToken": csrf_token 
        data:
          username: username
          password: password
        complete: (jqXHR) =>          
          if jqXHR.status == 200
            credentials = jqXHR.responseJSON
            post_log_message "login successful, username: #{ credentials.username }"
            post_message ["load_webviews"]
          else
            post_log_message "login failed (#{ jqXHR.status } #{ jqXHR.statusText }), response: #{ jqXHR.responseText }, please check credentials"
      $.ajax(settings)
      post_log_message "attempting login, username: #{ username }"

    enable_vkeyboard: () ->
      if $.fn.vkeyboard
        inputs = $(":input[type='number']")
        unless inputs.vkeyboard("instance")
          inputs.vkeyboard({layout: 'numeric'})
        inputs.vkeyboard("option", "disabled", false)
        post_log_message "[wv] vkeyboard enabled #{ inputs.length } inputs"
      
    disable_vkeyboard: () ->
      if $.fn.vkeyboard        
        inputs = $(":input[type='number']")
        unless inputs.vkeyboard("instance")
          inputs.vkeyboard({layout: 'numeric'})
        inputs.vkeyboard("option", "disabled", true)
        post_log_message "[wv] vkeyboard disabled #{ inputs.length } inputs"
      
  method = event.data[0]
  args = event.data[1..]
  result = functions[method].apply(functions, args)

window.addEventListener("message", dispatch, false)

