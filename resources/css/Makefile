# -*- mode: makefile-gmake; -*-

LESSC = lessc --no-color --strict-math=on
MINIFY = minify --no-comments

CSS_TARGETS = all_html5.css all_legacy.css all_html5.min.css all_legacy.min.css all_admin.css all_mailshot.css all_accounts.css all_admin_memberlist.css

.INTERMEDIATE: _wsrc_html5.css _wsrc_legacy.css _wsrc_accounts.css _wsrc_admin_memberlist.css
.SECONDARY: _jquery.mobile.structure.css _jquery-ui.css

all: $(CSS_TARGETS)

%.min.css: %.css
	$(MINIFY) $<

all_%.css: _wsrc_%.css jquery.mobile.icons.min.css svg-icons-homemade.css yellow_dots.css _jquery.mobile.structure.css jquery.bxslider.css
	cat  jquery.mobile.icons.min.css svg-icons-homemade.css yellow_dots.css  _jquery.mobile.structure.css jquery.bxslider.css $< > $@

all_admin.css: _jquery-ui.css jquery.loadmask.css wsrc_admin.css
	cat _jquery-ui.css jquery.loadmask.css wsrc_admin.css > $@

all_mailshot.css: _jquery-ui.css jquery.loadmask.css wsrc_mailshot.css
	cat _jquery-ui.css jquery.loadmask.css wsrc_mailshot.css > $@

all_accounts.css: _jquery-ui.css jquery.loadmask.css _wsrc_accounts.css
	cat _jquery-ui.css jquery.loadmask.css _wsrc_accounts.css > $@

all_admin_memberlist.css: _jquery-ui.css jquery.loadmask.css _wsrc_admin_memberlist.css
	cat _jquery-ui.css jquery.loadmask.css _wsrc_admin_memberlist.css > $@

_jquery.mobile.structure.css:
	wget http://ajax.googleapis.com/ajax/libs/jquerymobile/1.4.5/jquery.mobile.structure.css -O $@

_jquery-ui.css:
	wget http://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/themes/smoothness/jquery-ui.css -O $@

_wsrc_html5.css: wsrc.less
	$(LESSC) --global-var='iemode=false' $< > $@

_wsrc_legacy.css: wsrc.less
	$(LESSC) --global-var='iemode=true' $< > $@

_wsrc_accounts.css: wsrc_accounts.less
	$(LESSC) $< > $@

_wsrc_admin_memberlist.css: wsrc_admin_memberlist.less
	$(LESSC) $< > $@



