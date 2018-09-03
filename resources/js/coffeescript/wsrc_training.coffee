
class WSRCTraining_speech_synthesiser

  constructor: () ->
    @synth = window.speechSynthesis
    @rate = 1.0
    @pitch = 1.0
    @voice = null

  init: (voice_list_changed, voice_changed) ->
    @voice_changed = voice_changed
    handle_voices_changed = () =>
      voices = @synth.getVoices()
      voice_list_changed(voices)
    handle_voices_changed()
    if @synth.onvoiceschanged != undefined
      @synth.onvoiceschanged = handle_voices_changed
    
  create_utterance: (msg) ->
    utterance = new SpeechSynthesisUtterance(msg)
    utterance.pitch = @pitch
    utterance.rate = @rate
    utterance.voice = @voice
    return utterance

  utter: (utterance) ->
    @synth.speak(utterance)
    
  say: (msg) ->
    utterance = @create_utterance(msg)
    @utter(utterance)

  set_voice: (voice) ->
    @voice = voice
    @voice_changed()

  set_pitch: (val) ->
    @pitch = val
    @voice_changed()

  set_rate: (val) ->
    @rate = val
    @voice_changed()
  
class WSRCTraining_microphone

  constructor: (trigger, trigger_level, release_decay) ->

    @trigger = trigger
    @trigger_level = trigger_level || 0.98
    @release_decay = release_decay || 0.95
    @volume = 0

    # monkeypatch Web Audio
    window.AudioContext = window.AudioContext || window.webkitAudioContext
      
    # grab an audio context
    @audioContext = new AudioContext()

    didntGetStream = () =>
      alert('Unable to access your microphone. Please check your phone\'s settings.')

    gotStream = (stream) =>
      # Create an AudioNode from the stream.
      mediaStreamSource = @audioContext.createMediaStreamSource(stream)
      @processor = @audioContext.createScriptProcessor(512);
      @processor.onaudioprocess = (evt) => @volumeAudioProcess(evt);

    	# this will have no effect, since we don't copy the input to the output,
    	# but works around a current Chrome bug.
      @processor.connect(@audioContext.destination)
      mediaStreamSource.connect(@processor)

    # Attempt to get audio input
    try
      # monkeypatch getUserMedia
      navigator.getUserMedia = 
        navigator.getUserMedia ||
        navigator.webkitGetUserMedia ||
        navigator.mozGetUserMedia

      # ask for an audio input
      opts = 
        audio: 
          mandatory: 
            googEchoCancellation: "false"
            googAutoGainControl: "false"
            googNoiseSuppression: "false"
            googHighpassFilter: "false"
          optional: []
      navigator.getUserMedia(opts, gotStream, didntGetStream)
    catch e
      alert("ERROR - unable to access your microphone (#{ e }). Please check your phone's settings")

  shutdown: () ->
    @processor.disconnect()
    @processor.onaudioprocess = null

  volumeAudioProcess: (event) ->
    buf = event.inputBuffer.getChannelData(0)
    bufLength = buf.length
    sum = 0
  
    # Do a root-mean-square on the samples: sum up the squares...
    for i in [0...bufLength]
      x = buf[i]
      sum += x * x
  
    # ... then take the square root of the sum.
    rms =  Math.sqrt(sum / bufLength)
    if Math.abs(rms) >= @trigger_level
      trigger()
  
    # Add slow release to the sample:
    @volume = Math.max(rms, @volume*@release_decay)


class WSRCTraining

  constructor: () ->

    @canvasContext = document.getElementById( "meter" ).getContext("2d")
    @microphone = new WSRCTraining_microphone(@handle_voice_detected)
    @speech_synthesizer = new WSRCTraining_speech_synthesiser()

    voice_list_changed = (voices) => @handle_voice_list_changed(voices)
    accent_changed = () => @handle_accent_changed()
    @speech_synthesizer.init(voice_list_changed, accent_changed)

    @WIDTH = 500
    @HEIGHT = 50
    @detection_lag = 750
    @voice_last_detected = 0
    @rafID = 0

    voiceSelect = $('select[name="voices"]')
    voiceSelect.on("change", (obj) => @handle_voice_selected(obj))

  handle_voice_detected: () ->
    @voice_last_detected = window.performance.now();

  handle_voice_selected: (obj) ->
    selected = $('select[name="voices"] option:selected')
    voice = selected.data("voice")
    @speech_synthesizer.set_voice(voice)
    console.log("voice: " + voice.name)

  handle_accent_changed: () ->
    console.log("accent changed, voice: " + @speech_synthesizer.voice.name)
        
  handle_voice_list_changed: (voices) ->
    console.log("voice list changed")
    voiceSelect = $('select[name="voices"]')
    voiceSelect.children().remove()

    voices.sort (lhs, rhs) ->
      [lhs, rhs] = (x.name + x.lang for x in [lhs, rhs])
      return lhs.localeCompare(rhs)
    default_voice = null
    selected_voice_name = if @speech_synthesizer.voice then @speech_synthesizer.voice.name else ""
    for voice in voices
      default_txt = if voice.default then ", default" else ""
      text = "#{ voice.name } (#{ voice.lang }#{ default_txt })"
      value = "#{ voice.name }"
      if voice.lang == "en-GB"
        if voice.default
          default_voice = voice
        else if (not default_voice)
          default_voice = voice
      option = $("<option value='#{ value }'>#{ text }</option>")
      option.data("voice", voice)
      if voice.name == selected_voice_name
        option.prop("selected", true)        
      voiceSelect.append(option)
    unless @speech_synthesizer.voice
      if default_voice
        opt = voiceSelect.val(default_voice.name)
        opt.prop("selected", true)
        @speech_synthesizer.voice = default_voice


  drawLoop: (time) ->
    # clear the background
    @canvasContext.clearRect(0, 0, @WIDTH, @HEIGHT)

    if (@voice_last_detected + @detection_lag) > window.performance.now()
      @canvasContext.fillStyle = "red"
    else
      @canvasContext.fillStyle = "green"

    # draw a bar based on the current volume
    @canvasContext.fillRect(0, 0, @microphone.volume*@WIDTH*1.4, @HEIGHT)

    # set up the next visual callback
    @rafID = window.requestAnimationFrame((time) => @drawLoop(time))


unless window.wsrc?
  window.wsrc = {}
window.wsrc.training = WSRCTraining

