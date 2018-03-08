class WSRC_vkeyboard_controller
  constructor: (@_vkeyboard_container, @layout, parent) ->
    @_vkeyboard = $("<div class='vkeyboard'></div>").appendTo(@_vkeyboard_container)
    tabbable_set = parent.find(":input")
    @tabbable_set = $.makeArray(tabbable_set)
    get_tab_index = (elt) ->
      idx = elt.getAttribute("tabindex") or -1
      return parseInt(idx, 10)
    @tabbable_set.sort (lhs,rhs) ->
      return get_tab_index(lhs) - get_tab_index(rhs)
    @setup_vkeyboard()

  set_input: (@element) ->
    
  show: () ->
    @_vkeyboard_container.show()
    
  hide: () ->
    @_vkeyboard_container.hide()

  setup_vkeyboard: () ->
    keyset = if @_is_shift or @_is_caps then 'shift' else 'normal'
    if @_vkeyboard.data("keyset") != keyset
      @_layout_keyboard(@layout, keyset)
      @_vkeyboard.find("button").off("click").on("click", (evt) =>
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
      cls += " btn btn-default"
      jq_key = $("<button type='button' class='#{ cls }' data-action='#{ action }'>#{ key_face }</button>")
      jq_row.append(jq_key)
      
    setup_row = (jq_row, row_spec) =>
      for key in row_spec.split(" ")
        setup_key(jq_row, key)

    @_vkeyboard.data("keyset", keyset)

    @_vkeyboard.children().remove()    
    for row in this._layouts[layout][keyset]
      jq_row = $("<div class='keyboard-row'></div>")
      @_vkeyboard.append(jq_row)
      setup_row(jq_row, row)


  _handle_vkeypress: (evt) ->
    key = $(evt.target)
    action = key.data("action")
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
        @setup_vkeyboard()
    @element[0].focus()
    return undefined

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
    @setup_vkeyboard()
    return null
  _action_caps: () ->
    @_is_caps = not @_is_caps
    @setup_vkeyboard()
    return null
  _action_next: () ->
    @_tab_next()
    return false  
  _action_prev: () ->
    @_tab_prev()
    return false  
  _action_done: () ->
    @hide()
    return false
    
  _key_name_map:
    space: "&nbsp;"
    zero:  "0"
    minus:  "-"

  _tab_next: () ->
    set = @tabbable_set
    idx = set.indexOf(@element[0])
    if idx+1 < set.length
      set[idx+1].focus()
    else
      @element[0].focus()
    return false

  _tab_prev: () ->
    set = @tabbable_set
    idx = set.indexOf(@element[0])
    if idx-1 >= 0
      $(set[idx-1]).focus()
    else
      @element[0].focus()
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

  @get_instance: (layout, parent) ->
    container = $("#vkeyboard_container_#{ layout }")
    if container.length
      return container.data("vkeyboard_instance")
    container = $("<div class='vkeyboard_container' id='vkeyboard_container_#{ layout }'></div>")
    container.appendTo(parent)
    container.hide()
    instance = new WSRC_vkeyboard_controller(container, layout, parent)
    container.data("vkeyboard_instance", instance)
    return instance
    
    
vkeyboard_widget =

  options:
    layout: "qwerty"
    parent: $("body")
    
  _create: () ->
    @_instance = WSRC_vkeyboard_controller.get_instance(@options.layout, @options.parent)
    @element.on("focus", (evt, forced) =>
      @_instance.set_input(@element)
      unless forced
        @_show_vkeyboard()
    )

    # hide when parent form is submitted. Note: there is no way to
    # detect when the popup closes from an injected script.
    form = @element.parents("form")
    form.on "submit", () =>
      @_hide_vkeyboard()

  _show_vkeyboard: () ->
    unless @options.disabled
      @_instance.setup_vkeyboard()
      @_instance.show()

  _hide_vkeyboard: () ->
      @_instance.hide()


$.widget("wsrc.vkeyboard", vkeyboard_widget)
