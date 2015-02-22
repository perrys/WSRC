
class WSRC_ajax

  ##
  # Helper function for Ajax requests back to the server.
  # URL is the request url, should not include query params
  # DATA is an object which will be sent back as JSON
  # OPTS is an object containing:
  #  successCB - function to call back when successful
  #  failureCB - function to call back when there is an error
  #  csrf_token - (optional) CSRF token to be passed back to server
  # METHOD is the http CRUD type
  ## 
  @ajax_helper: (url, data, opts, method) ->
    jQuery.mobile.loading("show", 
      text: ""
      textVisible: false
      textonly: false
      theme: "a"
      html: ""
    )
    headers = {}
    if opts.csrf_token?
      headers["X-CSRFToken"] = opts.csrf_token
    settings =
      url: url
      type: method
      contentType: "application/json"
      data: JSON.stringify(data)
      headers: headers
      success: opts.successCB
      error: opts.failureCB
      complete: (xhr, status) ->
        jQuery.mobile.loading("hide") 
    if method == "GET"
      settings.dataType = "json" # expected return value
    else
      settings.processData = false
    jQuery.ajax(settings)
    return null

  @GET: (url, opts) ->
    this.ajax_helper(url, null, opts, "GET")

  @POST: (url, data, opts) ->
    this.ajax_helper(url, data, opts, "POST")
    
  @PUT: (url, data, opts) ->
    this.ajax_helper(url, data, opts, "PUT")


wsrc.utils.add_to_namespace("ajax", WSRC_ajax)