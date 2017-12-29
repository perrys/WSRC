
class WSRC_notifiers_view

  constructor: () ->
    @form = $('#notifiers_form')

  get_last_notifier: () ->
    fieldsets = @form.find("div.notifier_fieldset")
    for i in [fieldsets.length..1]
      unless fieldsets.eq(i-1).hasClass("toggled")
        return i
    return 0

  set_notifier_visibility: (n, isvisible) ->
    fieldset = @form.find("#fieldset-#{ n }")
    if isvisible
      fieldset.addClass("togglable").removeClass("toggled")
    else
      fieldset.removeClass("togglable").addClass("toggled")
      

  get_max_num_notifiers: () ->
    wsrc.utils.to_int(@form.find("input[name='form-MAX_NUM_FORMS']").val())
    
  set_notifier_deleted: (n, val) ->
    fieldset = @form.find("#fieldset-#{ n }")
    fieldset.find("input.delete").val(val)

  toggle_add_button: (disabled) ->
      @form.find("#add-notifier-button").prop("disabled", disabled)
    
  hide_status_messages: () ->
      @form.find(".form_success_message").hide()
      @form.find(".form_error_message").hide()
      
class WSRC_notifiers_controller

  constructor: () ->
    @view = new WSRC_notifiers_view()
    @view.form.find("#add-notifier-button").on("click", (evt) => @add_notifier(evt))
    @view.form.find("button.delete").on("click", (evt) => @remove_notifier(evt))

  add_notifier: (evt) ->
    last_notifier_number = @view.get_last_notifier()
    @view.set_notifier_visibility(last_notifier_number, true)
    @view.set_notifier_deleted(last_notifier_number, "")
    if last_notifier_number == (@view.get_max_num_notifiers()-1)
      @view.toggle_add_button(true)
    @view.hide_status_messages()
    return undefined
      
  remove_notifier: (evt) ->
    notifier_number = $(evt.target).parents(".notifier_fieldset").data("fieldset-id")
    @view.set_notifier_visibility(notifier_number, false)
    @view.set_notifier_deleted(notifier_number, "on")
    if notifier_number == (@view.get_max_num_notifiers()-1)
      @view.toggle_add_button(false)
    @view.hide_status_messages()
    return undefined
      
  @onReady: () ->
    @instance = new WSRC_notifiers_controller()
    

wsrc.notifiers = WSRC_notifiers_controller

