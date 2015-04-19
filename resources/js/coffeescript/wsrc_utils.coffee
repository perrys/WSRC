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

  @get_or_add_property: (obj, prop_name, factory) ->
    val = obj[prop_name]
    unless val
      val = factory()
      obj[prop_name] = val
    return val
    
  @numeric_sorter: (lhs, rhs, mapper) ->
    if mapper
      lhs = mapper(lhs)
      rhs = mapper(rhs)
    lhs = parseFloat(lhs)
    rhs = parseFloat(rhs)
    if isNaN(lhs)
      if isNaN(rhs)
        return 0
      return -1
    if isNaN(rhs)
      return 1
    return lhs - rhs

  @lexical_sorter: (lhs, rhs, mapper) ->
    if mapper
      lhs = mapper(lhs)
      rhs = mapper(rhs)
    (lhs > rhs) - (lhs < rhs)

  @lexical_sort: (array, field) ->
    sorter = (lhs, rhs) -> WSRC_utils.lexical_sorter(lhs[field], rhs[field]) 
    array.sort (sorter)
    return null

  @jq_stable_sort: (jq_list, sorter) ->
    items = []
    jq_list.each((idx, elt) ->
      elt.setAttribute("data-idx", idx)
      items.push(elt)
    )
    stable_sorter = (lhs,rhs) ->
      lhs = $(lhs)
      rhs = $(rhs)
      result = sorter(lhs, rhs)
      if result == 0
        result = lhs.data("idx") - rhs.data("idx")
      return result
    items.sort(stable_sorter)
    return items

  # returns a list of the given field's distinct values in the array,
  # ordered consistently with the input
  @unique_field_list: (array, field) ->
    unique_set = {}
    unique_list = []
    for o in array
      val = o[field]
      if unique_set[val]
        continue
      unique_set[val] = true
      unique_list.push(val)
    return unique_list
        
  @is_valid_int: (i) ->
    if i == ""
      return false
    i = parseInt(i)
    return not isNaN(i)

  @plural: (n, suffix) ->
    if n == 1
      return ''
    if suffix then suffix else 's'

  @toggle: (target_or_evt) ->
    target = target_or_evt
    if target_or_evt.target
      target = target_or_evt.target
    target = $(target)
    if target.hasClass("toggle-root")
      root = target
    else
      root = target.parents(".toggle-root")
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
    # dateformat: 2001-12-31
    toint = (start, len) -> parseInt(str.substr(start, len))
    new Date(toint(0,4), toint(5,2)-1, toint(8,2)) # gotcha - JS dates use 0-offset months...

  @british_to_js_date: (str) ->
    # dateformat: 31/12/2001
    toint = (start, len) -> parseInt(str.substr(start, len))
    new Date(toint(6,4), toint(3,2)-1, toint(0,2)) # gotcha - JS dates use 0-offset months...

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

  @add_object_if_unset: (root, name) ->
    unless root[name]
      root[name] = {}
    return root[name]

  @add_to_namespace: (name, obj) ->
    wsrc = WSRC_utils.add_object_if_unset(window, "wsrc")
    wsrc[name] = obj

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

  @apply_alt_class: (jq_rows, alt_class) ->
    odd = false
    jq_rows.each (idx, elt) ->
      jq_row = $(elt)
      if odd then jq_row.addClass(alt_class) else jq_row.removeClass(alt_class)
      odd = not odd
      return null

        
WSRC_utils.add_to_namespace("utils", WSRC_utils)
