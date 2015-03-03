unless window.assert?
  window.assert = (condition, message) ->
    unless condition 
      throw message || "Assertion failed"

class WSRC_utils
  
  @DAYS_OF_WEEK: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

  @list_lookup: (list, id, id_key) ->
    unless id_key?
      id_key = "id"
    for l in list
      if l[id_key] == id
        return l
    return null

  @is_valid_int: (i) ->
    if i == ""
      return false
    i = parseInt(i)
    return not isNaN(i)

  @toggle: (evt) ->
    root = $(evt.target).parents(".toggle-root")
    hiders = root.find(".togglable")
    showers = root.find(".toggled")
    hiders.removeClass("togglable").addClass("toggled")
    showers.removeClass("toggled").addClass("togglable")

  @get_ordinal_suffix: (i) ->
    if i in [11, 12, 13]
      return "th"
    r = i % 10    
    switch r
      when 1 then return "st"
      when 2 then return "nd"
      when 3 then return "rd"
      else return "th"

  @iso_to_js_date: (str) ->
    toint = (start, len) -> parseInt(str.substr(start, start+len))
    new Date(toint(0,4), toint(5,2)-1, toint(8,2)) # gotcha - JS dates use 0-offset months...

  @get_day_humanized: (basedate, offset) ->
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

  ##
  # Remove all items from the selector and replace with the given list
  ## 
  @fill_selector: (selector, list, selected_val) ->
    selector.find("option").remove()
    for item in list
      opt = jQuery("<option value='#{ item[0] }'>#{ item[1] }</option>")
      selector.append(opt)
      if item[0] == selected_val
        opt.prop('selected': true)
    selector.selectmenu();
    selector.selectmenu('refresh', true);
    return null

  @select: (selector, selected_val) ->
    selector.find("option").prop('selected': false)
    selector.find("option[value='#{ selected_val }']").prop('selected': true)
    selector.selectmenu('refresh', true);
    return null

  @add_to_namespace: (name, obj) ->
    unless window.wsrc
      window.wsrc = {}
    window.wsrc[name] = obj

  @partition: (jqitems, callback, val) ->
    filtered   = []
    unfiltered = []
    idx = 0
    for jq in jqitems
      dst = if callback.call(jq, idx++, val) then filtered else unfiltered
      dst.push(jq)
    return {
      filtered:   filtered
      unfiltered: unfiltered
    }
    
WSRC_utils.add_to_namespace("utils", WSRC_utils)