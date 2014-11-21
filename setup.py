#!/usr/bin/env python

from distutils.core import setup
import glob
import os.path

setup(name='WSRC',
      version='1.0',
      description='Woking Squash Club',
      author='Stewart Perry',
      author_email='stewart.c.perry@gmail.com',
      maintainer_email='webmaster@wokingsquashclub.org',
      url='http://www.wokingsquashclub.org/',
      packages=['wsrc', 
                'wsrc.booking', 
                'wsrc.utils', 
                'wsrc.site', 
                'wsrc.site.settings', 
                'wsrc.site.usermodel', 
                'wsrc.site.competitions',
                'wsrc.site.competitions.templatetags'],
      package_dir = {'wsrc': 'modules/wsrc',
                     'wsrc.booking': 'modules/wsrc/booking',
                     'wsrc.utils': 'modules/wsrc/utils',
                     'wsrc.site': 'modules/wsrc/site',
                     'wsrc.site.settings':  'modules/wsrc/site/settings',
                     'wsrc.site.usermodel': 'modules/wsrc/site/usermodel',
                     'wsrc.site.competitions':   'modules/wsrc/site/competitions',
                     'wsrc.site.competitions.templatetags':   'modules/wsrc/site/competitions/templatetags',
                     },
      package_data = {'wsrc': ['jinja2_templates/*.html', 'jinja2_templates/*.jinja2'],
                      'wsrc.site': ['templates/*.html'],
                      'wsrc.site.competitions': ['templates/*.html']
                      },
      scripts = ['scripts/wsrc'],
      data_files = [('etc', ['etc/notifier.json', 'etc/smtp.json']),
                    ('www/css', ['resources/css/main.css', 'resources/css/main_legacy.css']),
                    ('www/js', ['resources/js/main.js']),
                    ('www/images', glob.glob(os.path.join('resources', 'images', '*.jpg'))),
                    ]
     )