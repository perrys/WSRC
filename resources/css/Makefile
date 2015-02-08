# -*- mode: makefile-gmake; -*-

JINJACC = ../../tools/jinjac
MINIFY = minify --no-comments

CSS_TARGETS = all_html5.css all_legacy.css all_html5.min.css all_legacy.min.css admin.css

.INTERMEDIATE: _wsrc_html5.css _wsrc_legacy.css
.SECONDARY: _jquery.mobile.structure.css _jquery-ui.css

all: $(CSS_TARGETS)

%.min.css: %.css
	$(MINIFY) $<

all_%.css: _wsrc_%.css jqm_svg_icons_trimmed.css jqm_theme.css _jquery.mobile.structure.css jquery.bxslider.css
	cat jqm_svg_icons_trimmed.css jqm_theme.css _jquery.mobile.structure.css jquery.bxslider.css $< > $@

admin.css: _jquery-ui.css wsrc_admin.css
	cat _jquery-ui.css wsrc_admin.css > $@

_jquery.mobile.structure.css:
	wget http://ajax.googleapis.com/ajax/libs/jquerymobile/1.4.3/jquery.mobile.structure.css -O $@

_jquery-ui.css:
	wget http://ajax.googleapis.com/ajax/libs/jqueryui/1.11.2/themes/smoothness/jquery-ui.css -O $@

_wsrc_html5.css: wsrc.css
	$(JINJACC) $< ie_mode=0 > $@

_wsrc_legacy.css: wsrc.css
	$(JINJACC) $< ie_mode=1 > $@



