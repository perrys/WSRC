# -*- mode: makefile-gmake; -*-

LESSC = lessc --no-color --strict-math=on
MINIFY = minify --no-comments

CSS_TARGETS = wsrc_tournaments.css wsrc_courts.css wsrc_reflow_table.css wsrc_scores.css all_admin.css all_mailshot.css all_accounts.css all_admin_memberlist.css all_admin_boxes.css _jquery.mobile.datepicker.css

.INTERMEDIATE: _wsrc_html5.css _wsrc_legacy.css _wsrc_accounts.css _wsrc_admin_memberlist.css _wsrc_admin_boxes.css
.SECONDARY: _jquery.mobile.datepicker.css _jquery.dataTables.css _jquery-ui.css

all: $(CSS_TARGETS)

%.min.css: %.css
	$(MINIFY) $<

all_admin.css: _jquery-ui.css jquery.loadmask.css wsrc_admin.css
	cat _jquery-ui.css jquery.loadmask.css wsrc_admin.css > $@

all_mailshot.css: _jquery-ui.css jquery.loadmask.css wsrc_mailshot.css
	cat _jquery-ui.css jquery.loadmask.css wsrc_mailshot.css > $@

all_accounts.css: _jquery-ui.css jquery.loadmask.css _wsrc_accounts.css
	cat _jquery-ui.css jquery.loadmask.css _wsrc_accounts.css > $@

all_admin_memberlist.css: _jquery-ui.css _jquery.dataTables.css jquery.loadmask.css _wsrc_admin_memberlist.css
	cat _jquery-ui.css _jquery.dataTables.css jquery.loadmask.css _wsrc_admin_memberlist.css > $@

all_admin_boxes.css: _jquery-ui.css jquery.loadmask.css _wsrc_admin_boxes.css
	cat _jquery-ui.css jquery.loadmask.css _wsrc_admin_boxes.css > $@

_jquery-ui.css:
	wget http://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/themes/smoothness/jquery-ui.css -O $@

_jquery.dataTables.css:
	wget https://cdn.datatables.net/1.10.10/css/jquery.dataTables.css -O $@

_jquery.mobile.datepicker.css:
	wget https://rawgithub.com/arschmitz/jquery-mobile-datepicker-wrapper/master/jquery.mobile.datepicker.css -O $@

wsrc_%.css: less/%.less
	$(LESSC)  $< > $@

_wsrc_accounts.css: wsrc_accounts.less
	$(LESSC) $< > $@

_wsrc_admin_memberlist.css: wsrc_admin_memberlist.less
	$(LESSC) $< > $@

_wsrc_admin_boxes.css: wsrc_admin_boxes.less
	$(LESSC) $< > $@



