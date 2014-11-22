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




