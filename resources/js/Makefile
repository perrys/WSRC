# -*- mode: makefile-gmake; -*-

COFFEECC = coffee -c
MINIFY = minify --no-comments

.SECONDARY: _jquery.js _jquery.mobile.js

all: all.min.js

%.js: %.coffee
	coffee -c $<

%.min.js: %.js
	$(MINIFY) $< -o $@

all.js: wsrc.js _jquery.js _jquery.mobile.js pre_jqm.js
	cat _jquery.js pre_jqm.js _jquery.mobile.js $< > $@

_jquery.js:
	wget http://ajax.googleapis.com/ajax/libs/jquery/1.11.1/jquery.js -O $@

_jquery.mobile.js:
	wget http://ajax.googleapis.com/ajax/libs/jquerymobile/1.4.3/jquery.mobile.js -O $@
