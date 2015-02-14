# -*- mode: makefile-gmake; -*-

COFFEECC = coffee -c
MINIFY = minify --no-comments

.SECONDARY: _jquery.js _jquery.mobile.js _jquery-ui.js

all: all.min.js all_admin.js

%.js: coffeescript/%.coffee
	coffee -c -p $< > $@

%.min.js: %.js
	$(MINIFY) $< -o $@

ORDERED_MAIN_JS_SRCS = _jquery.js pre_jqm.js _jquery.mobile.js legacy_shims.js jquery.bxslider.js wsrc_utils.js wsrc_ajax.js wsrc_homepage.js wsrc_result_form.js wsrc.js 

all.js: $(ORDERED_MAIN_JS_SRCS)
	cat $(ORDERED_MAIN_JS_SRCS) > $@

all_admin.js: _jquery.js _jquery-ui.js jquery.loadmask.js wsrc_admin.js
	cat _jquery.js _jquery-ui.js jquery.loadmask.js wsrc_admin.js > $@

_jquery.js:
	wget http://ajax.googleapis.com/ajax/libs/jquery/1.11.1/jquery.js -O $@


_jquery.mobile.js:
	wget http://ajax.googleapis.com/ajax/libs/jquerymobile/1.4.3/jquery.mobile.js -O $@

_jquery-ui.js:
	wget https://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/jquery-ui.js -O $@
