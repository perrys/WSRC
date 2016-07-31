WSRC
====

Squash Tournament Web Application

prerequisites:

Pip:

```sh
$ apt-get -y install python-pip
```

MySQL: either:

```sh
$ apt-get -y install python-mysqldb
```

or:

```sh
$ pip install mysqlclient
```

```sh
$ pip install Django==1.6
$ pip install djangorestframework==3.0.2
$ pip install django-coverage 
$ pip install markdown              # Markdown support for the browsable API.
$ pip install django-filter==0.9.1  # Filtering support
$ pip install beautifulsoup4
$ pip insatll Jinja2
$ pip install --upgrade google-api-python-client
$ pip install xlrd
$ pip install xlsxwriter
```

for development:

```sh
$ apt-get -y install npm
$ npm install -g coffee-script@1.8.0
$ npm install -g minify@1.4.3
$ npm install -g util-io@1.7.0
$ npm install -g less@2.5.0
```