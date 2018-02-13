class WSRC_Tournament

  @HIGHLIGHT_CLASS: "wsrc-highlight"
    
  constructor: (@match_create_url, @no_navigation_flag) ->
    @bind_tournament_events()
    
  bind_tournament_events: () ->
    playerElts = jQuery("td.player")
    playerElts.unbind()
    
    playerElts = playerElts.filter(":not(td.empty-match)")
    playerElts.mouseenter (evt) =>
      target = $(evt.target)
      myteam = target.data("team")
      unless myteam
        return false
      matches = jQuery("td.player").filter () ->
        theirteam = $(this).data("team")
        return myteam == theirteam
      matches.addClass(wsrc.Tournament.HIGHLIGHT_CLASS)
    playerElts.mouseleave (evt) =>      
      jQuery("td.#{ wsrc.Tournament.HIGHLIGHT_CLASS }").removeClass(wsrc.Tournament.HIGHLIGHT_CLASS)

    # Bail out here unless authenticated
    unless WSRC_username
      return null

    # score entry bindings:
    open_score_entry_dialog = (elt) =>
      matchId = parseInt($(elt).data("match"), 10);
      query = if @no_navigation_flag then "?no_navigation" else ""
      document.location.href="#{ @match_create_url }/#{ matchId }#{ query }"
      
    playerElts = playerElts.filter(":not(td.partial-match)")
    playerElts = playerElts.filter(":not(td.completed-match)")

    playerElts.dblclick (evt) ->
      open_score_entry_dialog(evt.target)
    playerElts.on "taphold", (evt) ->
      open_score_entry_dialog(evt.target)
    
    playerElts.siblings().filter(".score").dblclick (evt) ->
      target = evt.target;
      while not target.classList.contains("player") # TODO - support older browsers
        target = target.previousSibling
      open_score_entry_dialog(target)

    return null

      
window.wsrc.Tournament = WSRC_Tournament
