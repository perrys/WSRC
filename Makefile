# -*- mode: makefile-gmake; -*-


JS_SRCS  = resources/js/main.js


.PHONY: build build_js build_css install dist

build: build_css build_js

build_css:
	$(MAKE) -C resources/css

build_js:
	$(MAKE) -C resources/js

install: build 
	python ./setup.py install

bdist: build
	python ./setup.py bdist

bdist_windows: build
	python ./setup.py bdist_wininst


etags: 
	etags `find modules -name '*.py'` \
	`find resources -name '*.coffee'` \
	`find resources -name 'wsrc_*.css'` \
	`find modules -name '*.html'`

