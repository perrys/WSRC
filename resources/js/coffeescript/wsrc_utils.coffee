unless window.assert?
  window.assert = (condition, message) ->
    unless condition 
      throw message || "Assertion failed"

window.WSRC_utils =
  
  DAYS_OF_WEEK: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

  set_on_and_off: (onid, offid) ->
    jQuery("##{ onid }").show()
    jQuery("##{ offid }").hide()

  list_lookup: (list, id, id_key) ->
    unless id_key?
      id_key = "id"
    for l in list
      if l[id_key] == id
        return l
    return null

  is_valid_int: (i) ->
    if i == ""
      return false
    i = parseInt(i)
    return not isNaN(i)

  toggle: (evt) ->
    root = $(evt.target).parents(".toggle-root")
    hiders = root.find(".togglable")
    showers = root.find(".toggled")
    hiders.removeClass("togglable").addClass("toggled")
    showers.removeClass("toggled").addClass("togglable")

  get_ordinal_suffix: (i) ->
    if i in [11, 12, 13]
      return "th"
    r = i % 10    
    switch r
      when 1 then return "st"
      when 2 then return "nd"
      when 3 then return "rd"
      else return "th"

  iso_to_js_date: (str) ->
    toint = (start, len) -> parseInt(str.substr(start, start+len))
    new Date(toint(0,4), toint(5,2)-1, toint(8,2)) # gotcha - JS dates use 0-offset months...

  get_day_humanized: (basedate, offset) ->
    switch offset
      when 0 then return "Today"
      when 1 then return "Tomorrow"
      when -1 then return "Yesterday"
    dt = this.iso_to_js_date(basedate)
    dt.setDate(dt.getDate() + offset)
    dow = this.DAYS_OF_WEEK[dt.getDay()]
    dom = dt.getDate()
    suffix = this.get_ordinal_suffix(dom)
    return "#{ dow } #{ dom }#{ suffix }"
