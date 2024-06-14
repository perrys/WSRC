FROM grahamdumpleton/mod-wsgi-docker:python-2.7-onbuild
#COPY /etc/ssl/certs/ca-certificates.crt .
CMD [ "hello.wsgi" ]
#COPY ./public-html/ /usr/local/apache2/htdocs/
