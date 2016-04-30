
vkeyboard_widget =

  options:
    layout: "qwerty"
    
  _create: () ->
    @_initialize_vkeyboard()
    console.log(@element)
    @element.on("focus", (evt, forced) =>
      unless forced
        @_show_vkeyboard()
    )

  _initialize_vkeyboard: () ->
    @_vkeyboard = $('#vkeyboard')
    unless @_vkeyboard.length
      container = $("<div id='vkeyboard_container'></div>").appendTo($("body"))
      container.hide()
      @_vkeyboard = $("<div id='vkeyboard'></div>").appendTo(container)

  _show_vkeyboard: () ->
    @_setup_vkeyboard()
    @_vkeyboard.parents("#vkeyboard_container").show()

  _hide_vkeyboard: () ->
    @_vkeyboard.parents("#vkeyboard_container").hide()

  _setup_vkeyboard: () ->
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

  _tab_next: () ->
    parent = @element.parents("form")
    set = parent.find(":tabbable")
    idx = set.index(@element)
    if idx+1 < set.length
      set.eq(idx+1).focus()
    return false

  _tab_prev: () ->
    parent = @element.parents("form")
    set = parent.find(":tabbable")
    idx = set.index(@element)
    if idx-1 >= 0
      set.eq(idx-1).focus()
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
        '7 8 9 {prev}'
        '4 5 6 {next}'
        '1 2 3 {clear}'
        '{zero} - {done}'
      ]

$.widget("wsrc.vkeyboard", vkeyboard_widget)
