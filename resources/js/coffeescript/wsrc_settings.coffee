
class WSRC_settings_model

  constructor: (@user_event_filters) ->

class WSRC_settings_view

  constructor: () ->
    @form = $('#settings_form')

  toggle_notifier_inputs: () ->
    target = @form.find('#court_notifier_inputs')
    wsrc.utils.toggle(target)

  get_notifier_uidays: () ->
    days = @form.find("input[name='ui-days']:checked")
    l = []
    days.each (idx, elt) ->
      l.push($(elt).val())
    return l

  set_notifier_days_input: (days) ->
    @form.find("input[name='days']").val(days.toString())
      
class WSRC_settings_controller

  constructor: (@model) ->
    @view = new WSRC_settings_view()
    @view.form.find("input[name='ui-days']").on("change", () =>
      @notifier_days_changed()
    )

  toggle_notifier_inputs: () ->
    @view.toggle_notifier_inputs()
      
  notifier_days_changed: () ->
    days = @view.get_notifier_uidays()
    @view.set_notifier_days_input(days)
      
  @onReady: (user_event_filters) ->
    model = new WSRC_settings_model(user_event_filters)
    @instance = new WSRC_settings_controller(model)
    
  @on: (method) ->
    args = $.fn.toArray.call(arguments)
    @instance[method].apply(@instance, args[1..])


wsrc.settings = WSRC_settings_controller

