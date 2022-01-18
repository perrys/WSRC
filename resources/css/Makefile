# -*- mode: makefile-gmake; -*-

LESSC = lessc --no-color --strict-math=on --source-map-rootpath=.
MINIFY = minify 

CSS_TARGETS = _jquery.mobile.datepicker.css wsrc_common.css wsrc_courts.css wsrc_tournaments.css wsrc_reflow_table.css wsrc_scores.css \
              wsrc_jquery.vkeyboard.css

.SECONDARY: _jquery.mobile.datepicker.css _jquery.dataTables.css _jquery-ui.css
.PHONY: all

all: all.css all.min.css all_admin.css all_admin_boxes.css all_mailshot.css all_accounts.css

%.min.css: %.css
	$(MINIFY) $< > $@

all.css:  $(CSS_TARGETS)
	cat $(CSS_TARGETS) > $@

all_admin.css: _jquery-ui.css jquery.loadmask.css wsrc_admin.css
	cat _jquery-ui.css jquery.loadmask.css wsrc_admin.css > $@

all_mailshot.css: _jquery-ui.css jquery.loadmask.css wsrc_mailshot.css
	cat _jquery-ui.css jquery.loadmask.css wsrc_mailshot.css > $@

all_accounts.css: _jquery-ui.css jquery.loadmask.css wsrc_admin_accounts.css
	cat _jquery-ui.css jquery.loadmask.css wsrc_admin_accounts.css > $@

all_admin_boxes.css: _jquery-ui.css jquery.loadmask.css wsrc_admin_boxes.css
	cat _jquery-ui.css jquery.loadmask.css wsrc_admin_boxes.css > $@

_jquery-ui.css:
	wget http://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/themes/smoothness/jquery-ui.css -O $@

_jquery.dataTables.css:
	wget https://cdn.datatables.net/1.10.10/css/jquery.dataTables.css -O $@

_jquery.mobile.datepicker.css:
	wget https://rawgithub.com/arschmitz/jquery-mobile-datepicker-wrapper/master/jquery.mobile.datepicker.css -O $@

wsrc_%.css: less/%.less
	$(LESSC)  $< > $@




