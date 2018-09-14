#!/usr/bin/env python

from distutils.core import setup
import glob
import os.path

def get_images(pathelts):
    images = []
    for ext in [".jpg", ".ico", ".png", ".gif", ".svg"]:
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
                'wsrc.site.templatetags',
                'wsrc.site.settings',
                'wsrc.site.usermodel',
                'wsrc.site.usermodel.migrations',
                'wsrc.site.accounts',
                'wsrc.site.courts',
                'wsrc.site.courts.migrations',
                'wsrc.site.competitions',
                'wsrc.site.competitions.migrations',
                'wsrc.site.competitions.templatetags',
                'wsrc.site.email',
      ],
      package_dir = {'wsrc': 'modules/wsrc',
                     'wsrc.external_sites': 'modules/wsrc/external_sites',
                     'wsrc.utils': 'modules/wsrc/utils',
                     'wsrc.site': 'modules/wsrc/site',
                     'wsrc.site.templatetags': 'modules/wsrc/site/templatetags',
                     'wsrc.site.settings':  'modules/wsrc/site/settings',
                     'wsrc.site.accounts':  'modules/wsrc/site/accounts',
                     'wsrc.site.courts':    'modules/wsrc/site/courts',
                     'wsrc.site.competitions':   'modules/wsrc/site/competitions',
                     'wsrc.site.competitions.templatetags':   'modules/wsrc/site/competitions/templatetags',
                     'wsrc.site.email':    'modules/wsrc/site/email',
                     },
      package_data = {'wsrc.site': ['templates/*.html', 'templates/*.txt', 'templates/admin/*.html', 'templates/admin/*.csv', \
                                    'templates/admin/courts/*/*.html', 'templates/admin/usermodel/*/*.html'],
                      'wsrc.site.competitions': ['templates/*.html', 'templates/*.csv'],
                      'wsrc.site.accounts': ['templates/*.html'],
                      'wsrc.site.courts': ['templates/*.html'],
                      'wsrc.site.usermodel': ['templates/*.html']
                      },
      scripts = ['scripts/wsrc'],
      data_files = [('www/css', glob.glob(os.path.join('resources', 'css', 'all*.css'))),
                    ('www/js', [os.path.join('resources', 'js', 'jquery.vkeyboard.js'), \
                                os.path.join('resources', 'js', 'legacy_shims.js')] +\
                     glob.glob(os.path.join('resources', 'js', 'all*.js'))),
                    ('www/images', get_images(['resources', 'images'])),
                    ('www/css/images', get_images(['resources', 'css', 'images'])),
                    ('www/css/images/icons-png', glob.glob(os.path.join('resources', 'images', 'icons-png', '*.png'))),
                    ]
     )
