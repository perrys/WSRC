`if ( 'function' !== typeof Array.prototype.reduce ) {
  Array.prototype.reduce = function( callback /*, initialValue*/ ) {
    'use strict';
    if ( null === this || 'undefined' === typeof this ) {
      throw new TypeError(
         'Array.prototype.reduce called on null or undefined' );
    }
    if ( 'function' !== typeof callback ) {
      throw new TypeError( callback + ' is not a function' );
    }
    var t = Object( this ), len = t.length >>> 0, k = 0, value;
    if ( arguments.length >= 2 ) {
      value = arguments[1];
    } else {
      while ( k < len && ! k in t ) k++; 
      if ( k >= len )
        throw new TypeError('Reduce of empty array with no initial value');
      value = t[ k++ ];
    }
    for ( ; k < len ; k++ ) {
      if ( k in t ) {
         value = callback( value, t[k], k, t );
      }
    }
    return value;
  };
}
`
  
window.WSRC =

  BASE_URL: "."
  
  toggle: (onid, offid) ->
    jQuery("##{ onid }").css("display", "")
    jQuery("##{ offid }").css("display", "none")

  league_config: null

  findMatching: (list, id) ->
    for l in list
      if l.id == id
        return l
    return null

  ##
  # Remove non-empty items from the selector and replace with the given list
  ## 
  bulkAdd: (selector, list) ->
    elt = selector[0] # get the DOM element
    for i in [(elt.options.length-1)..1] by -1
      if elt.options[i].value != ""
        elt.remove(i)
    for item in list
      selector.append("<option value='#{ item }'>#{ item }</option>")
    selector.selectmenu();
    selector.selectmenu('refresh', true);
    return null
    
  ##
  # Helper function to show a modal click-through dialog
  ##
  showErrorDialog: (msg) ->
    jQuery("#errorPopupDialog div[role='main'] h3").html(msg)
    jQuery("#errorPopupDialog").popup()
    jQuery("#errorPopupDialog").popup("open")
    return true

  ##
  # Helper function for Ajax requests back to the server.
  # OPTS is an object containing:
  #  successCB - function to call back when successful
  #  failureCB - function to call back when there is an error
  #  loadMaskId (optional) - ID of HTML element to show a loadmask over
  ## 
  loadFromServer: (url, opts) ->
    jQuery.mobile.loading( "show", 
      text: ""
      textVisible: false
      textonly: false
      theme: "a"
      html: ""
    )
    jQuery.ajax(
      url: this.BASE_URL + url
      type: "GET"
      dataType: "json"
      success: opts.successCB
      error: opts.failureCB
      complete: (xhr, status) ->
        jQuery.mobile.loading( "hide" ) 
    )
    return true

  openBoxDetailDialog: (id) ->
    id = id.replace("link-", "")
    jQuery.mobile.changePage("#boxDetailDialog");
    box_config = this.findMatching(this.league_config.boxes, id)
    dialogdiv = jQuery("div#boxDetailDialog")
    dialogdiv.find("div h2").text(box_config.name)
    form = dialogdiv.find("form#addChangeForm")
    players = (p for p in box_config.players)
    players.sort()
    this.bulkAdd(form.find("select#player1"), players)
    this.bulkAdd(form.find("select#player2"), players)
    return null

  playerSelected: (id) ->
    form = jQuery("div#boxDetailDialog form#addChangeForm")
    selector = form.find("select##{ id }")
    selected = selector.val()
    form.find("table#score-entry-input th#header-#{ id }").text(selected)
    otherid = (id == "player2") and "player1" or "player2"
    otherselector = form.find("select##{ otherid }")
    if otherselector.val() == ""
      players = (p.value for p in selector.find("option") when (p.value != "" and p.value != selected))
      this.bulkAdd(otherselector, players)
    
  createBoxes: (league_config) ->
    maxplayers = (b.players.length for b in league_config.boxes).reduce (x,y) -> Math.max(x,y)

    createBoxTable = (box_config) ->
      tbl = jQuery("<table data-role='table' data-mode='' id='table-#{ box_config.id }' class='boxes ui-corner-all ui-table'>")
      html = "<thead><tr><th colspan='2'></th>" +
        ("<td class='ui-bar-a'>#{ i }</td>" for i in [1..maxplayers]).join("") +
        "</tr></thead>"
      tbl.append(html)
      rows = []
      for i in [1..maxplayers]
        player = box_config.players[i-1] ? "" 
        html = "<tbody><th>#{ player }</td><td class='ui-bar-a'>#{ i }</td>"
        for j in [1..maxplayers]
          if j == i
            html += "<td class='ui-bar-a'> </td>"
          else
            html += "<td> </td>"
        html += "</tbody>"
        rows.push(html)
      tbl.append(rows.join(""))

    maindiv = jQuery("body div#boxes div[role='main']")
    wrapperdiv = null
    for box_config in league_config.boxes
      doublecolumn = box_config.doublecolumn?
      secondcolumn = doublecolumn and wrapperdiv?
      unless secondcolumn
        colspec = doublecolumn and "double" or "single"
        wrapperdiv = jQuery("<div class='ui-grid-a boxes-wrapper boxes-wrapper-#{ colspec }column'>")
        wrapperdiv.trigger("create")
      extraclasses = ""
      if doublecolumn
        extraclasses = "boxes-" + (secondcolumn and "second" or "first") + "column ui-block-" + (secondcolumn and "b" or "a")
      boxdiv = jQuery("<div class='ui-corner-all custom-corners boxes #{ extraclasses }'>")
      boxdiv.append("<div class='ui-bar ui-bar-a'><h2>#{ box_config.name }</h2><a id='link-#{ box_config.id }' href='#' onclick='WSRC.openBoxDetailDialog(this.id); return false;' class='ui-btn ui-icon-action ui-btn-icon-notext ui-corner-all ui-btn-right'></a></div>")
      tablediv = jQuery("<div class='ui-body ui-body-a'>")
      tablediv.append(createBoxTable(box_config))
      boxdiv.append(tablediv)
      boxdiv.trigger("create")
      wrapperdiv.append(boxdiv)
      if not doublecolumn or secondcolumn
        maindiv.append(wrapperdiv)
      unless doublecolumn and not secondcolumn
        wrapperdiv = null
    return null


  onReady: () ->
    url = "/data/boxes.json"
    this.loadFromServer(url,
      successCB: (config) =>
        this.league_config = config
        this.createBoxes(config)
        return true
      failureCB: (xhr, status) => 
        this.showErrorDialog("ERROR: Failed to load data from #{ url }")
        return true
    )

    