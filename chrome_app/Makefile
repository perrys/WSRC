# -*- mode: makefile-gmake; -*-

COFFEECC = coffee -c
LESSC = lessc --no-color --strict-math=on
ZIP = zip

.SECONDARY: _jquery.js _jquery.mobile.js _jquery-ui.js

CSS_FILES = window.css jquery.mobile.structure.css jquery.mobile.icons.css jquery.vkeyboard.css
JS_FILES  = window.js background.js client_functions.js jq_settings.js _jquery.js _jquery.mobile.js _jquery-ui.js jquery.vkeyboard.js

CSS_TARGETS = $(addprefix css/,$(CSS_FILES))
JS_TARGETS  = $(addprefix js/,$(JS_FILES))

all: $(CSS_TARGETS) $(JS_TARGETS)

js/_jquery.js:
	wget http://ajax.googleapis.com/ajax/libs/jquery/1.11.1/$(subst js/_,,$@) -O $@

js/_jquery.mobile.%:
	wget http://ajax.googleapis.com/ajax/libs/jquerymobile/1.4.5/$(subst js/_,,$@) -O $@

js/_jquery-ui.%:
	wget https://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/$(subst js/_,,$@) -O $@

css/jquery.mobile.%:
	wget http://ajax.googleapis.com/ajax/libs/jquerymobile/1.4.5/$(subst css/,,$@) -O $@

js/%.js: js/coffeescript/%.coffee
	coffee -c -p $< > $@

css/%.css: css/less/%.less
	$(LESSC) $< > $@

app.zip: $(CSS_TARGETS) $(JS_TARGETS)
	$(ZIP) $@ manifest.json window.html css/*.css js/*.js images/* css/images/*
