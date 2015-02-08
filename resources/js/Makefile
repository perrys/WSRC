# -*- mode: makefile-gmake; -*-

COFFEECC = coffee -c
MINIFY = minify --no-comments

.SECONDARY: _jquery.js _jquery.mobile.js _jquery-ui.js

all: all.min.js wsrc_admin.js

%.js: %.coffee
	coffee -c $<

%.min.js: %.js
	$(MINIFY) $< -o $@

all.js: wsrc.js _jquery.js _jquery.mobile.js pre_jqm.js legacy_shims.js jquery.bxslider.js 
	cat _jquery.js pre_jqm.js _jquery.mobile.js legacy_shims.js jquery.bxslider.js $< > $@

wsrc_admin.js: _jquery-ui.js admin.js
	cat _jquery-ui.js admin.js > $@

_jquery.js:
	wget http://ajax.googleapis.com/ajax/libs/jquery/1.11.1/jquery.js -O $@


_jquery.mobile.js:
	wget http://ajax.googleapis.com/ajax/libs/jquerymobile/1.4.3/jquery.mobile.js -O $@

_jquery-ui.js:
	wget https://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/jquery-ui.js -O $@
