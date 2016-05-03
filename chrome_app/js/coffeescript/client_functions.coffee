

dispatch = (event) ->
  
  functions =
  
    get_username: () ->
      return $("input[name='current_username']").val()

  method = event.data[0]
  args = event.data[1..]
  result = functions[method].apply(functions, args)
  results = {
    method: method
    args:   args
    result: result
  }
  event.source.postMessage(results, event.origin)

window.addEventListener("message", dispatch, false)

$(":input[type='number']").vkeyboard({layout: 'numeric'})
