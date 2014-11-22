# -*- mode: makefile-gmake; -*-

JINJACC = ../../tools/jinjac
MINIFY = minify --no-comments

CSS_TARGETS = all_html5.min.css all_legacy.min.css

.INTERMEDIATE: _wsrc_html5.css _wsrc_legacy.css
.SECONDARY: _jquery.mobile.structure.css

all: $(CSS_TARGETS)

%.min.css: %.css
	$(MINIFY) $<

all_%.css: _wsrc_%.css jqm_theme.css _jquery.mobile.structure.css
	cat jqm_theme.css _jquery.mobile.structure.css $< > $@

_jquery.mobile.structure.css:
	wget http://ajax.googleapis.com/ajax/libs/jquerymobile/1.4.3/jquery.mobile.structure.css -O $@

_wsrc_html5.css: wsrc.css
	$(JINJACC) $< ie_mode=0 > $@

_wsrc_legacy.css: wsrc.css
	$(JINJACC) $< ie_mode=1 > $@



