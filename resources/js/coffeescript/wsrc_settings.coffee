
class WSRC_settings_view

  constructor: () ->
    @form = $('#settings_form')

  get_last_notifier: () ->
    fieldsets = @form.find("div.notifier_fieldset")
    visible=0
    fieldsets.each (idx, elt) ->
      if $(elt).hasClass("toggled")
        return false
      ++visible
    return visible

  set_notifier_visibility: (n, isvisible) ->
    fieldset = @form.find("div.notifier_fieldset").eq(n-1)
    if isvisible
      fieldset.addClass("togglable").removeClass("toggled")
    else
      fieldset.removeClass("togglable").addClass("toggled")
      

  get_initial_notifiers: () ->
    wsrc.utils.to_int(@form.find("input[name='form-INITIAL_FORMS']").val())
    
  set_notifier_deleted: (n, val) ->
    fieldset = @form.find("div.notifier_fieldset").eq(n-1)
    fieldset.find("input.delete").val(val)
      
class WSRC_settings_controller

  constructor: () ->
    @view = new WSRC_settings_view()
    @view.form.find("#add-notifier-button").on("click", (evt) => @add_notifier(evt))
    @view.form.find("#remove-notifier-button").on("click", (evt) => @remove_notifier(evt))

  add_notifier: (evt) ->
    evt.stopPropagation()
    last_notifier_number = @view.get_last_notifier()
    @view.set_notifier_visibility(last_notifier_number+1, true)
    @view.set_notifier_deleted(last_notifier_number+1, "")
    return false
      
  remove_notifier: (evt) ->
    evt.stopPropagation()
    last_notifier_number = @view.get_last_notifier()
    @view.set_notifier_visibility(last_notifier_number, false)
    if last_notifier_number <= @view.get_initial_notifiers()
      @view.set_notifier_deleted(last_notifier_number, "on")
    return false
      
  @onReady: () ->
    @instance = new WSRC_settings_controller()
    

wsrc.settings = WSRC_settings_controller

