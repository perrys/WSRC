INSTALLDIR = /var/www

INSTALL = install
SED = sed

IMG_SRCS = $(notdir $(wildcard resources/images/*))
CSS_SRCS = $(notdir $(wildcard resources/css/*.css))
JS_SRCS  = restful.js jquery.loadmask.js jquery.cookie.js webtoolkit_md5.js

TARGETS = $(INSTALLDIR)/index.html $(INSTALLDIR)/wsrc/wsrc.wsgi $(INSTALLDIR)/wsrc/wsrc_server.py $(INSTALLDIR)/wsrc/lib/Database.py \
	$(addprefix $(INSTALLDIR)/resources/js/,$(JS_SRCS)) \
	$(addprefix $(INSTALLDIR)/resources/images/,$(IMG_SRCS)) \
	$(addprefix $(INSTALLDIR)/resources/css/,$(CSS_SRCS)) \


install: $(TARGETS)

$(INSTALLDIR)/index.html: scripts/bracket_generator.py $(wildcard scripts/jinja-templates/*.html)
	scripts/bracket_generator.py > $@

resources/js/restful.js: resources/js/restful.coffee
	coffee -c $<

$(INSTALLDIR)/wsrc/%.py: %.py
	$(INSTALL) -D $< $@

$(INSTALLDIR)/wsrc/%.wsgi: %.wsgi
	$(INSTALL) -d $(dir $@)
	$(SED) s%@TARGETDIR%$(dir $@)% $< > $@

$(INSTALLDIR)/wsrc/lib/%.py: lib/%.py
	$(INSTALL) -D $< $@

$(INSTALLDIR)/resources/images/%: resources/images/%
	$(INSTALL) -D $< $@

$(INSTALLDIR)/resources/css/%.css: resources/css/%.css
	$(INSTALL) -D $< $@

$(INSTALLDIR)/resources/js/%.js: resources/js/%.js
	$(INSTALL) -D $< $@
