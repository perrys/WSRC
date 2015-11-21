
window.WSRC_homepage =

  MONTHS_OF_YEAR: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

  refresh_facebook: (data) ->
    # Loads facebook feed from server (used as proxy to FB) and popultes the table
    table = $("#facebook_news tbody").show()
    if data? and data.data.length > 0
      trim_words = (text) ->
        return text.split(/\s+/).slice(0,10).join(" ") + "&hellip;"
      table.find("tr").remove()
      odd = true
      for e in data.data[0..10]
        dt = e.updated_time
        dt = dt.substring(8,10) + " " + this.MONTHS_OF_YEAR[parseInt(dt.substring(5,7))-1]
        title = if e.message? then e.message else e.description
        unless title
          continue
        title = trim_words(title)
        link = if e.link? then e.link else "http://www.facebook.com/#{ e.id }" 
        row = $("<tr><td class='nobreak'><a href='#{ link }'>#{ dt }</td><td>#{ title }</td></tr>")
        if odd
          row.addClass("odd")
          odd = false
        else
          row.addClass("even")
          odd = true
        table.append(row)

  add_empty_slots: (bookings) ->
    # Scan todays bookings and insert empty court slots
    if bookings.length == 0
      return bookings
      
    date_prefix = bookings[0].start_time.substr(0,11)
    
    COURT_SLOT_LENGTH = 45
    COURT_START_TIMES =
      1: (8.5  * 60)
      2: (8.75 * 60)
      3: (9    * 60)
    
    abs_minutes = (tstr) ->
      60 * parseInt(tstr.substr(11,13)) + parseInt(tstr.substr(14,16))
    totimestr = (i) ->
      hours = Math.floor(i / 60)
      mins = i % 60
      doubleint = (i) -> if i < 10 then "0" + i else "" + i
      return "#{ doubleint(hours) }:#{ doubleint(mins) }"
    result = []
    
    court_to_bookings_map = {1: [], 2: [], 3: []}
    court_to_gaps_map = {1: [], 2: [], 3: []}

    for b in bookings
      start_end = [abs_minutes(b.start_time), abs_minutes(b.end_time)]
      court_to_bookings_map[b.court].push(start_end)
    for court,booking_list of court_to_bookings_map
      last_end_mins = 0
      for b in booking_list
        gap = b[0] - last_end_mins
        if gap > 0
          court_to_gaps_map[court].push([last_end_mins, last_end_mins + gap])
        last_end_mins = b[1]
      gap = (24 * 60) - last_end_mins
      if gap > 0
        court_to_gaps_map[court].push([last_end_mins, last_end_mins + gap])
        
    is_booked = (court, slot_start) ->
      gaps = court_to_gaps_map[court]
      for gap in gaps
        if gap[1] < slot_start
          continue
        if (gap[0] <= slot_start) and gap[1] >= (slot_start + COURT_SLOT_LENGTH)
          return false
        return true
          
    newlist = []
    for court, start of COURT_START_TIMES
      while start < (22.5 * 60)
        unless is_booked(court, start)
          newlist.push
            start_time:  date_prefix + totimestr start
            end_time:    date_prefix + totimestr (start + COURT_SLOT_LENGTH)
            court:       court
            name:        "_"
        start += COURT_SLOT_LENGTH

    return bookings.concat(newlist)
        
  display_court_bookings: (data, day_offset, addLinks) ->
    
    day_offset = if day_offset then parseInt(day_offset) else 0
      
    if Math.abs(day_offset) > 7
      return
      
    if day_offset == 7
      $("#btn_booking_next").hide()
      $("#btn_booking_previous").show()
    else if day_offset == -7
      $("#btn_booking_next").show()
      $("#btn_booking_previous").hide()
    else
      $("#btn_booking_next").show()
      $("#btn_booking_previous").show()
    
    table = $("#evening_bookings tbody").show()
    
    if data
      table.find("tr").remove()
      slots = if day_offset >= 0 then this.add_empty_slots(data) else data
      slots.sort (lhs, rhs) ->
        (lhs.start_time > rhs.start_time) - (lhs.start_time < rhs.start_time)
      odd = true
      alinkdiv = $('#booking_seeall_toggle')
      toggleclass = if alinkdiv.hasClass("toggled") then "togglable" else "toggled"
      for booking in slots
        t1 = booking.start_time
        t2 = booking.end_time
        getTimeElt = (start, len, t) ->
          unless t?
            t = t1
          t.substring(start, start+len)
        getTime = (t) ->
          getTimeElt(11, 5, t)
        name = booking.name
        if booking.name == "_"
          if addLinks
            name = "<a href='http://www.court-booking.co.uk/WokingSquashClub/edit_entry_fixed.php?room=#{ booking.court }&area=1&hour=#{ getTimeElt(11,2) }&minute=#{ getTimeElt(14,2) }&year=#{ getTimeElt(0,4) }&month=#{ getTimeElt(5,2) }&day=#{ getTimeElt(8,2) }'>(available)</a>"
        else
          name = booking.name
        cls = if parseInt(getTimeElt(11,2)) < 17 then toggleclass else ""
        row = $("<tr class='#{ cls }'><td>#{ getTime(t1) }&ndash;#{ getTime(t2) }</td><td>#{ name }</td><td>ct.&nbsp;#{ booking.court }</td></tr>")
        row.addClass(if odd then "odd" else "even")
        odd = not odd
        table.append(row)
    return null

  booking_advance: (days) ->
    # Reload court bookings for appropriate date after one of the buttons has been pressed
    table = $("#evening_bookings")
    container = table.parents(".jqm-block-content")
    basedate = table.data("basedate")
    dayoffset = parseInt(table.data("dayoffset"))
    dayoffset += days
    url = "/data/bookings?date=#{ basedate }&day_offset=#{ dayoffset }"    
    wsrc.ajax.GET(url,
      successCB: (data) =>
        table.data("dayoffset", dayoffset)
        container.find("h4").html(wsrc.utils.get_day_humanized(basedate, dayoffset))
        this.display_court_bookings(data, dayoffset, WSRC_user_player_id?)
        return true
      failureCB: (xhr, status) =>
        table.find("tbody").hide()
        err_container = container.find("p").show()
        err_container.html(xhr.responseText)    
        return false
    )

