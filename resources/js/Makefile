
# -*- mode: makefile-gmake; -*-

COFFEECC = coffee -c
MINIFY = minify 

.SECONDARY: _jquery.js _jquery-ui.js _jquery.dataTables.js

all: all.min.js all_admin.js all_admin_mailshot.js all_admin_accounts.js all_admin_boxes.js

%.js: coffeescript/%.coffee
	coffee -c -p $< > $@

%.min.js: %.js
	$(MINIFY) $< > $@

ORDERED_MAIN_JS_SRCS = wsrc_utils.js wsrc_homepage.js wsrc_notifiers.js wsrc_court_booking.js wsrc_tournaments.js wsrc_result_form.js

all.js: $(ORDERED_MAIN_JS_SRCS) jquery.vkeyboard.js 
	cat $(ORDERED_MAIN_JS_SRCS) > $@

all_admin.js: _jquery.js _jquery-ui.js jquery.loadmask.js wsrc_utils.js wsrc_admin.js
	cat _jquery.js _jquery-ui.js jquery.loadmask.js wsrc_utils.js wsrc_admin.js > $@

all_admin_mailshot.js: _jquery.js _jquery-ui.js jquery.loadmask.js wsrc_utils.js wsrc_ajax.js wsrc_admin_mailshot.js
	cat _jquery.js _jquery-ui.js jquery.loadmask.js wsrc_utils.js wsrc_ajax.js wsrc_admin_mailshot.js > $@

all_admin_accounts.js: _jquery.js _jquery-ui.js jquery.loadmask.js wsrc_utils.js wsrc_ajax.js wsrc_admin_accounts.js
	cat _jquery.js _jquery-ui.js jquery.loadmask.js wsrc_utils.js wsrc_ajax.js wsrc_admin_accounts.js > $@

all_admin_boxes.js: _jquery.js _jquery-ui.js jquery.loadmask.js wsrc_utils.js wsrc_ajax.js wsrc_boxes.js
	cat _jquery.js _jquery-ui.js jquery.loadmask.js wsrc_utils.js wsrc_ajax.js wsrc_boxes.js > $@

_jquery.js:
	wget http://ajax.googleapis.com/ajax/libs/jquery/1.11.1/jquery.js -O $@


_jquery-ui.js:
	wget https://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/jquery-ui.js -O $@

_jquery.ui.datepicker.js:
	wget https://rawgithub.com/jquery/jquery-ui/1-10-stable/ui/jquery.ui.datepicker.js -O $@

_jquery.dataTables.js:
	wget https://cdn.datatables.net/1.10.10/js/jquery.dataTables.js -O $@
