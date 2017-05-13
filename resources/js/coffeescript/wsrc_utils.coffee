unless window.assert?
  window.assert = (condition, message) ->
    unless condition 
      throw message || "Assertion failed"

class WSRC_utils
  
  @MONTHS_OF_YEAR: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  @DAYS_OF_WEEK: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
  
  @list_lookup: (list, id, id_key, converter) ->
    unless id_key?
      id_key = "id"
    for l in list
      val = l[id_key]
      if converter
        val = converter(val)
      if val == id
        return l
    return null

  @list_of_tuples_to_map: (l) ->
    amap = {}
    reducer = (result, item) ->
      result[item[0]] = item[1]
      return result
    l.reduce(reducer, amap)
    return amap 

  @list_to_map: (l, id_key) ->
    amap = {}
    reducer = (result, item) ->
      result[item[id_key]] = item
      return result
    l.reduce(reducer, amap)
    return amap 

  # like Array.prototype.reduce - loops over the attributes of an object
  @reduce_object: (obj, func, start_val) ->
    for key, val of obj
      start_val = func(start_val, val)
    return start_val

  @cantor_pair: (n1, n2) ->
    if n1 < 0 or n2 < 0
      raise "error: non-positive number passed to cantor pair, n1=#{ n1 }, n=#{ n2 }"      
    result = (n1 + n2) * (n1 + n2 + 1) / 2 + n1
    if ! Number.isSafeInteger(result)
      raise "error: cantor pair overflow, n1=#{ n1 }, n=#{ n2 }"
    return result

  @get_property_list: (obj) ->
    l = (k for k,v of obj)
    return l

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

  @jq_stable_sort: (jq_list, sorter, reverse) ->
    items = []
    jq_list.each((idx, elt) ->
      elt.setAttribute("data-idx", idx)
      items.push(elt)
    )
    stable_sorter = (lhs,rhs) ->
      lhs = $(lhs)
      rhs = $(rhs)
      result = sorter(lhs, rhs)
      if reverse
        result = -result
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

  @to_int: (str) ->
    return parseInt(str, 10)

  @iso_to_js_date: (str) ->
    # dateformat: 2001-12-31
    toint = (start, len) => @to_int(str.substr(start, len))
    new Date(toint(0,4), toint(5,2)-1, toint(8,2)) # gotcha - JS dates use 0-offset months...
    
  @iso_to_js_datetime: (dt_str) ->
    y = this.toint(dt_str.substr(0,4))
    m = this.toint(dt_str.substr(5,2))
    d = this.toint(dt_str.substr(8,2))
    ho = this.toint(dt_str.substr(11,2))
    mi = this.toint(dt_str.substr(14,2))
    se = this.toint(dt_str.substr(17,4))
    offset_mi = 0
    if dt_str.length >= 25
      offset_ho = this.toint(dt_str.substr(20,2))
      offset_mi = this.toint(dt_str.substr(23,2))
      offset_mi += offset_ho * 60
      if dt_str.substr(19,1) != "-"
        offset_mi = offset_mi * -1
    date = new Date(Date.UTC(y, m-1, d, ho, mi + offset_mi, se)) 
    return date

  @british_to_js_date: (str) ->
    # dateformat: 31/12/2001
    toint = (start, len) => @to_int(str.substr(start, len))
    new Date(toint(6,4), toint(3,2)-1, toint(0,2)) # gotcha - JS dates use 0-offset months...

  @js_to_iso_date_str: (dt) ->
    # do not use toISOString() as it uses UTC and will introduce day offsets in summer time
    pad_zeros = (n) ->
      if n < 10 then "0#{ n }" else n
    return "#{ dt.getFullYear() }-#{ pad_zeros(dt.getMonth()+1) }-#{ pad_zeros(dt.getDate()) }"

  @js_to_readable_date_str: (dt, omit_year, dow_break) ->
    dow = this.DAYS_OF_WEEK[dt.getDay()][0..2]
    dom = dt.getDate()
    month = this.MONTHS_OF_YEAR[dt.getMonth()]
    year = dt.getFullYear()
    suffix = this.get_ordinal_suffix(dom)
    unless dow_break
      dow_break = " "
    result = "#{ dow }#{ dow_break }#{ dom }#{ suffix } #{ month }"
    unless omit_year
      result += " #{ year }"
    return result

  @js_to_12h_time_str: (dt, with_am_pm) ->
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
    
  @is_same_date: (d1, d2) ->
    d1.getFullYear() == d2.getFullYear() && 
    d1.getMonth()    == d2.getMonth() && 
    d1.getDate()     == d2.getDate()

  @sum: (l) ->
    sum = 0.0
    for a in l
      sum += a
    return sum
    
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

  @map_by_id: (alist) ->
    amap = {}
    for item in alist
      amap[item.id] = item
    return amap

  @apply_alt_class: (jq_rows, alt_class) ->
    odd = false
    jq_rows.each (idx, elt) ->
      jq_row = $(elt)
      if odd then jq_row.addClass(alt_class) else jq_row.removeClass(alt_class)
      odd = not odd
      return null

  @configure_sortable: (jq_elt) ->
    jq_elt.off("click")

    jq_root = jq_elt.parents(".sortable-root")
    jq_parent = jq_root.find(".sortable-parent")
    selector = jq_elt.data("selector")

    sorter_func = wsrc.utils[jq_elt.data("sorter")]
    sorter = (lhs, rhs) ->
      mapper = (row) ->
        jq_td = $(row).find(selector)
        sortval = jq_td.data("sortvalue")
        unless sortval
          sortval = jq_td.text()
        return sortval
      sorter_func(lhs, rhs, mapper)

    handler = () ->    
      elts = jq_parent.children().remove()
      reverse = jq_elt.data("reverse")
      unless reverse?
        reverse = true
      sorted_elts = wsrc.utils.jq_stable_sort(elts, sorter, reverse)
      if reverse
        jq_elt.data("reverse", false)
      else
        jq_elt.data("reverse", true)
      for child in sorted_elts
        jq_parent.append(child)
      wsrc.utils.apply_alt_class(jq_parent.children(), "alt")

    jq_elt.on("click", (evt) ->
      handler()
    )
    return handler

  @configure_sortables: () ->
    $(".sortable").each (idx, elt) ->
      handler = WSRC_utils.configure_sortable($(elt))
    
        
WSRC_utils.add_to_namespace("utils", WSRC_utils)
