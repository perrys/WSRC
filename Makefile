# -*- mode: makefile-gmake; -*-


CSS_SRCS = resources/css/main.css resources/css/main_legacy.css
JS_SRCS  = resources/js/main.js


.PHONY: build install dist

build: $(CSS_SRCS) $(JS_SRCS)

install: build
	python ./setup.py install

bdist: build
	python ./setup.py bdist

resources/js/%.js: resources/js/%.coffee
	coffee -c $<

resources/css/main.css: resources/css/_main.css
	./tools/jinjac $< ie_mode=0 > $@

resources/css/main_legacy.css: resources/css/_main.css
	./tools/jinjac $< ie_mode=1 > $@

