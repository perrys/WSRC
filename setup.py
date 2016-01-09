#!/usr/bin/env python

from distutils.core import setup
import glob
import os.path

def get_images(pathelts):
  images = []
  for ext in [".jpg", ".ico", ".png"]:
    elts = list(pathelts)
    elts.append('*'+ext)
    pattern = os.path.join(*elts)
    images.extend(glob.glob(pattern))
  return images

setup(name='WSRC',
      version='1.0',
      description='Woking Squash Club',
      author='Stewart Perry',
      author_email='stewart.c.perry@gmail.com',
      maintainer_email='webmaster@wokingsquashclub.org',
      url='http://www.wokingsquashclub.org/',
      packages=['wsrc', 
                'wsrc.external_sites', 
                'wsrc.utils', 
                'wsrc.site', 
                'wsrc.site.settings', 
                'wsrc.site.usermodel', 
                'wsrc.site.accounts', 
                'wsrc.site.competitions',
                'wsrc.site.competitions.templatetags'],
      package_dir = {'wsrc': 'modules/wsrc',
                     'wsrc.external_sites': 'modules/wsrc/external_sites',
                     'wsrc.utils': 'modules/wsrc/utils',
                     'wsrc.site': 'modules/wsrc/site',
                     'wsrc.site.settings':  'modules/wsrc/site/settings',
                     'wsrc.site.usermodel': 'modules/wsrc/site/usermodel',
                     'wsrc.site.accounts': 'modules/wsrc/site/accounts',
                     'wsrc.site.competitions':   'modules/wsrc/site/competitions',
                     'wsrc.site.competitions.templatetags':   'modules/wsrc/site/competitions/templatetags',
                     },
      package_data = {'wsrc': ['jinja2_templates/*.html', 'jinja2_templates/*.jinja2'],
                      'wsrc.site': ['templates/*.html'],
                      'wsrc.site.competitions': ['templates/*.html'],
                      'wsrc.site.accounts': ['templates/*.html']
                      },
      scripts = ['scripts/wsrc'],
      data_files = [('www/css', glob.glob(os.path.join('resources', 'css', 'all_*.css'))),
                    ('www/js', glob.glob(os.path.join('resources', 'js', 'all*.js'))),
                    ('www/images', get_images(['resources', 'images'])),
                    ('www/css/images', get_images(['resources', 'css', 'images'])),
                    ('www/css/images/icons-png', glob.glob(os.path.join('resources', 'images', 'icons-png', '*.png'))),
                    ]
     )
