#!/usr/bin/env python

from distutils.core import setup

setup(name='WSRC',
      version='1.0',
      description='Woking Squash Club',
      author='Stewart Perry',
      author_email='stewart.c.perry@gmail.com',
      maintainer_email='webmaster@wokingsquashclub.org',
      url='http://www.wokingsquashclub.org/',
      packages=['wsrc', 'wsrc.booking', 'wsrc.utils', 'wsrc.jinja2_templates'],
      package_dir = {'wsrc': 'python',
                     'wsrc.booking': 'python/booking',
                     'wsrc.utils': 'python/utils',
                     },
      package_data = {'wsrc': ['jinja2_templates/*.html', 'jinja2_templates/*.jinja2']},
      scripts = ['scripts/wsrc'],
      data_files = [('etc', ['etc/notifier.json', 'etc/smtp.json'])
                    ]
     )
