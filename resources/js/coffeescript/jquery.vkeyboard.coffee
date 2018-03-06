vkeyboard_widget =

  options:
    layout: "qwerty"
    
  _create: () ->
    @_initialize_vkeyboard()
    @element.on("focus", (evt, forced) =>
      unless forced
        @_show_vkeyboard()
    )

    # if this is a popup append to the popup container to avoid
    # problems with the screen mask
    get_parent_popup = (elt) ->
      role = elt.data("role")
      if role == "popup"
        return elt
      parent = elt.parent()
      if parent.length
        return get_parent_popup(parent)
      return parent
      
    @_popup_parent = get_parent_popup(@element)

    # hide when parent form is submitted. Note: there is no way to
    # detect when the popup closes from an injected script.
    form = @element.parents("form")
    form.on "submit", () =>
      console.log("form submit")
      @_hide_vkeyboard()

  _initialize_vkeyboard: () ->
    @_vkeyboard_container = $('#vkeyboard_container')
    if @_vkeyboard_container.length
      @_vkeyboard = $('#vkeyboard')
    else
      @_vkeyboard_container = $("<div id='vkeyboard_container'></div>").appendTo("body")
      @_vkeyboard_container.hide()
      @_vkeyboard = $("<div id='vkeyboard'></div>").appendTo(@_vkeyboard_container)
      parent = @element.parents("form")
      tabbable_set = parent.find(":tabbable")
      tabbable_set = $.makeArray(tabbable_set)
      @_vkeyboard.data("tabbable_set", tabbable_set)

  _show_vkeyboard: () ->
    unless @options.disabled
      @_setup_vkeyboard()
      @_vkeyboard_container.show()

  _hide_vkeyboard: () ->
    @_vkeyboard_container.hide()

  _setup_vkeyboard: () ->
    target = if @_popup_parent.length then @_popup_parent.eq(0) else $("body")
    @_vkeyboard_container.detach()
    target.append(@_vkeyboard_container)
    
    layout = @options.layout
    keyset = if @_is_shift or @_is_caps then 'shift' else 'normal'
    require_layout = true
    if @_vkeyboard.data("layout") == layout
      if @_vkeyboard.data("keyset") == keyset
        require_layout = false
    else
      @_is_shift = @_is_caps = false # reset on layout switch
    if require_layout
      @_layout_keyboard(layout, keyset)
    this._vkeyboard.find("button").off("click").on("click", (evt) =>
      @_handle_vkeypress(evt)
    )

  _layout_keyboard: (layout, keyset) ->

    setup_key = (jq_row, key_spec) =>
      cls = "key"
      action = ""
      if /^\{\S+\}$/.test(key_spec)
        key_spec = key_spec.substr(1, key_spec.length-2)
        cls = action = key_spec
        key_face = if @_key_name_map[key_spec] then @_key_name_map[key_spec] else key_spec
      else
        key_face = key_spec      
      jq_key = $("<button class='#{ cls }' data-action='#{ action }'>#{ key_face }</button>")
      jq_row.append(jq_key)
      
    setup_row = (jq_row, row_spec) =>
      for key in row_spec.split(" ")
        setup_key(jq_row, key)

    @_vkeyboard.data("layout", layout)
    @_vkeyboard.data("keyset", keyset)

    @_vkeyboard.children().remove()    
    for row in this._layouts[layout][keyset]
      jq_row = $("<div class='keyboard-row'></div>")
      @_vkeyboard.append(jq_row)
      setup_row(jq_row, row)


  _handle_vkeypress: (evt) ->
    key = $(evt.target)
    action = $(key).data("action")
    if action
      action_fn = @["_action_#{ action }"]
      char = action_fn.call(this, key)
      if char == false
        return
    else
      char = key.text()
    if char
      this.element.val(this.element.val() + char)
      if @_is_shift
        @_is_shift = false
        @_setup_vkeyboard()
    this.element.trigger("focus", true)      

  _action_tab: () -> return "	"
  _action_space: () -> return " "
  _action_zero: () -> return "0"
  _action_minus: () ->
    val = parseInt(this.element.val(), 10)
    unless isNaN(val)
      val = -1 * val
      this.element.val("#{ val }")
      return null
  _action_bksp: () ->
    val = this.element.val()
    if val
      val = val.substr(0, val.length-1)
      this.element.val(val)
    return null
  _action_clear: () ->
    this.element.val("")
    return null
  _action_shift: () ->
    @_is_shift = not @_is_shift
    @_setup_vkeyboard()
    return null
  _action_caps: () ->
    @_is_caps = not @_is_caps
    @_setup_vkeyboard()
    return null
  _action_next: () ->
    @_tab_next()
    return false  
  _action_prev: () ->
    @_tab_prev()
    return false  
  _action_done: () ->
    @_hide_vkeyboard()
    return false
    
  _key_name_map:
    space: "&nbsp;"
    zero:  "0"
    minus:  "-"

  _tab_set: () ->
    set = @_vkeyboard.data("tabbable_set")
    get_tab_index = (elt) ->
      idx = elt.getAttribute("tabindex") or -1
      return parseInt(idx, 10)
    set.sort (lhs,rhs) ->
      return get_tab_index(lhs) - get_tab_index(rhs)
    return set

  _tab_next: () ->
    set = @_tab_set()
    idx = set.indexOf(@element[0])
    if idx+1 < set.length
      set[idx+1].focus()
    return false

  _tab_prev: () ->
    set = @_tab_set()
    idx = set.indexOf(@element[0])
    if idx-1 >= 0
      $(set[idx-1]).focus()
    return false

  _layouts:
    qwerty:
      normal: [
        '` 1 2 3 4 5 6 7 8 9 0 - = {bksp}'
        '{tab} q w e r t y u i o p [ ] \\'
        '{caps} a s d f g h j k l ; \' {enter}'
        '{shift} z x c v b n m , . / {shift}'
        '{prev} {next} {space} {clear} {done}'
      ]
      shift: [
        '~ ! " # $ % ^ & * ( ) _ + {bksp}'
        '{tab} Q W E R T Y U I O P { } |'
        '{caps} A S D F G H J K L : @ {enter}'
        '{shift} Z X C V B N M < > ? {shift}'
        '{prev} {next} {space} {clear} {done}'
      ]
    numeric: 
      normal: [
        '7 8 9 {clear}'
        '4 5 6 {next}'
        '1 2 3 {prev}'
        '{zero} {minus} {done}'
      ]

$.widget("wsrc.vkeyboard", vkeyboard_widget)
