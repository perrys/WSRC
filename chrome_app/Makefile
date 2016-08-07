# -*- mode: makefile-gmake; -*-

COFFEECC = coffee -c
LESSC = lessc --no-color --strict-math=on
ZIP = zip
VERSION = $(shell date --utc +%Y.%m.%d.%H%M)
DATE = $(shell date --utc +%Y-%m-%dT%H:%M)
HOST = $(shell hostname)

.SECONDARY: jq_jquery.js jq_jquery.mobile.js jq_jquery-ui.js

CSS_FILES = window.css jquery.mobile.structure.css jquery.mobile.icons.css jquery.vkeyboard.css
JS_FILES  = window.js background.js client_functions.js wsrc_utils.js jq_settings.js jq_jquery.js jq_jquery.mobile.js jq_jquery-ui.js jquery.vkeyboard.js

CSS_TARGETS = $(addprefix css/,$(CSS_FILES))
JS_TARGETS  = $(addprefix js/,$(JS_FILES))

all: $(CSS_TARGETS) $(JS_TARGETS) manifest.json

js/jq_jquery.js:
	wget http://ajax.googleapis.com/ajax/libs/jquery/1.11.1/$(subst js/jq_,,$@) -O $@

js/jq_jquery.mobile.%:
	wget http://ajax.googleapis.com/ajax/libs/jquerymobile/1.4.5/$(subst js/jq_,,$@) -O $@

js/jq_jquery-ui.%:
	wget https://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/$(subst js/jq_,,$@) -O $@

css/jquery.mobile.%:
	wget http://ajax.googleapis.com/ajax/libs/jquerymobile/1.4.5/$(subst css/,,$@) -O $@

js/%.js: js/coffeescript/%.coffee
	coffee -c -p $< > $@

css/%.css: css/less/%.less
	$(LESSC) $< > $@

manifest.json: manifest.json.template
	sed 's/{version}/$(VERSION)/;s/{date}/$(DATE)/;s/{host}/$(HOST)/' $< > $@

app.zip: $(CSS_TARGETS) $(JS_TARGETS)  manifest.json
	$(ZIP) $@ manifest.json window.html css/*.css js/*.js images/* css/images/*
