WSRC
====

Squash Tournament Web Application

prerequisites:

```sh
sudo -H bash
```

Pip:

```sh
apt-get -y install python-pip
```

MySQL: either:

```sh
apt-get -y install python-mysqldb
```

or:

```sh
pip install mysqlclient
```

```sh
pip install setuptools
pip install Django==1.6
pip install djangorestframework==3.0.2
pip install markdown              # Markdown support for the browsable API.
pip install beautifulsoup4
pip install xlrd
pip install xlsxwriter
pip install iCalendar
pip install django-debug-toolbar==1.4

# old modules, no longer required:
pip install django-coverage 
pip install django-filter==0.9.1  # Filtering support
pip insatll Jinja2
pip install --upgrade google-api-python-client
```

for development:

```sh
apt-get -y install npm
npm install -g coffee-script@1.8.0
npm install -g minify@1.4.3
npm install -g util-io@1.7.0
npm install -g less@2.5.0
npm install -g babel-cli
npm install -g babel-preset-env
npm install -g decaffeinate
npm install -g bootstrap@3

```

