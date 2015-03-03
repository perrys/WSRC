                  
window.WSRC =

  competitiongroup_data: null

  bxslider_inited: false

  ##
  # Helper function to show a modal click-through dialog
  ##
  show_error_dialog: (msg) ->
    # close any open popups
    allpopups = jQuery("div[data-role=popup]")
    idx = 0
    openpopups = []
    while (idx < allpopups.length)
      apopup = allpopups.eq(idx)
      if apopup.parent().hasClass("ui-popup-active")
        openpopups.push(apopup)
        apopup.popup("close")
      idx += 1
    popupdiv = jQuery("#errorPopupDialog")
    popupdiv.find("div.ui-content h3").html(msg)
    popupdiv.popup(
      afterclose: (event, ui) =>
        for apopup in openpopups
          apopup.popup("open")
    )
    popupdiv.popup("open")
    return true


  onBoxActionClicked: (link) ->
    WSRC_leagues.open_box_detail_popup(link.id)

  onTournamentSelected: (selector) ->
    $.mobile.loading("show")
    link = $(selector).val()
    document.location = link

  onLeagueSelected: (selector) ->
    $.mobile.loading("show")
    link = "/boxes/" + $(selector).val()
    document.location = link

  onTournamentPageShow: (page) ->
    competition_id = page.data().competitionid

    refresh_tournament_data = (data) ->
      page_dirty_callback = () ->
        loadPageData()
      controller = new wsrc.Tournament(data, page_dirty_callback)
      page.data("tournament", controller)
      return true
      
    url = "/data/competition/#{ competition_id }?expand=1"
    loadPageData = () =>
      wsrc.ajax.GET(url,
        successCB: refresh_tournament_data
        failureCB: (xhr, status) => 
          this.show_error_dialog("ERROR: Failed to load tournament data from #{ url }")
          return false
      )
    $("#bracket-refresh-button").click (evt) ->
      loadPageData()
    refresh_tournament_data(WSRC_bracket_data)

  onLeaguePageShow: (page) ->
    competitiongroup_id = page.data().competitiongroupid
      
    url = "/data/competitiongroup/#{ competitiongroup_id }?expand=1"
    loadPageData = () =>
      wsrc.ajax.GET(url,
        successCB: (data) =>
          return true
        failureCB: (xhr, status) => 
          this.show_error_dialog("ERROR: Failed to load data from #{ url }")
          return false
      )
    $("#box-refresh-button").click (evt) ->
      loadPageData()
    WSRC_leagues.refresh_all_box_data(WSRC_box_data)

    view_radios = $("#page-control-form input[name='view_type']")
    view_radios.on("change", (evt) ->
      view_type = view_radios.filter(":checked").val()
      if view_type == "tables"
        $("table.boxtable").hide()
        $("table.leaguetable").show()
      else
        $("table.leaguetable").hide()
        $("table.boxtable").show()
    )
    
  onHomePageShow: (page) ->

    $(".toggle-link a").on("click", wsrc.utils.toggle)

    url = "/data/facebook"    
    wsrc.ajax.GET(url,
      successCB: (data) =>
        WSRC_homepage.refresh_facebook(data)
        return true
      failureCB: (xhr, status) =>
        table = $("#facebook_news tbody").hide()
        err_container = table.parents(".jqm-block-content").find("p").show()
        err_container.html(xhr.responseText)    
        return false
    )
    unless this.bxslider_inited
      $('.bxslider').bxSlider(
        mode: 'horizontal',
        slideWidth: 460,
        captions: false,
        randomStart: true,
        controls: false,
        auto: true,
        pause: 7000,
      );
      this.bxslider_inited = true
    WSRC_homepage.display_court_bookings(WSRC_today_bookings, 0, WSRC_user_player_id?)
    return true

  onPageContainerShow: (evt, ui) ->
    newpage = ui.toPage
    pagetype = newpage.data().pagetype
    if pagetype == "home"
      this.onHomePageShow(newpage)
    else if pagetype == "boxes"
      this.onLeaguePageShow(newpage)
    else if pagetype == "tournament"
      this.onTournamentPageShow(newpage)
    else if pagetype == "memberlist"
      document.getElementById("filterTable-input").focus()
    else if pagetype == "login"
      document.getElementById("id_username").focus()

    # TODO - check why this is here ??
    $("#box_link").click(() ->
      document.location.pathname="/competitions/leagues"
    )

    location.search.substr(1).split("&").forEach( (pair) ->
      if (pair == "")
        return
      parts = pair.split("=")
      if parts[0] == "scrollto"
        callback = () -> $.mobile.silentScroll($("#" + parts[1])[0].offsetTop)
        window.setTimeout(callback, 500)
      else if parts[0] == "filter-ids"
        filterable = $(".wsrc-filterable")
        items = filterable.children()
        ids = parts[1].split(",")
        partitioned = wsrc.utils.partition(items, (idx, val) ->
          id = $(this).data("wsrcfilter").toString()
          return ids.indexOf(id) >= 0
        )
        $( partitioned.unfiltered ).addClass( "ui-screen-hidden" )
        $( partitioned.filtered ).removeClass( "ui-screen-hidden" )
    )

  
if window.WSRC_deferedPageContainerShow
  [event, ui] = WSRC_deferedPageContainerShow
  WSRC.onPageContainerShow(event, ui)
