# -*- mode: makefile-gmake; -*-


JS_SRCS  = resources/js/main.js


.PHONY: build build_js build_css install dist clean etags update_npm

build: build_css build_js

build_using_docker:

update_npm:
	npm install

build_css: update_npm
	PATH=${PATH}:${PWD}/node_modules/.bin $(MAKE) -C resources/css

build_js: update_npm
	PATH=${PATH}:${PWD}/node_modules/.bin $(MAKE) -C resources/js

install: build 
	docker run -u`id -u`:`id -g` -v .:/mnt --entrypoint /mnt/run_docker_build.sh grahamdumpleton/mod-wsgi-docker:python-2.7-onbuild 
	mkdir -p install/certs
	cp /etc/ssl/certs/ca-certificates.crt install/certs
	docker build -f Dockerfile -t wsrc install

clean:
	/bin/rm -rf build install
	find . -name '*.pyc' -exec /bin/rm {} \;

etags: 
	etags `find modules -name '*.py'` \
	`find resources -name '*.coffee'` \
	`find resources -name 'wsrc_*.css'` \
	`find resources -name 'wsrc_*.less'` \
	`find modules -name '*.html'`

