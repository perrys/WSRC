$(document).bind("mobileinit", () ->
  opts =
    # disable HTML5 features not allowed in apps
    autoInitializePage: true
    pushStateEnabled: false
    hashListeningEnabled: false
  $.extend($.mobile, opts)
)
