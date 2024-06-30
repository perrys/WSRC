FROM grahamdumpleton/mod-wsgi-docker:python-2.7-onbuild
ENV DEBIAN_FRONTEND=noninteractive
#COPY /etc/ssl/certs/ca-certificates.crt .
#COPY ./public-html/ /usr/local/apache2/htdocs/
