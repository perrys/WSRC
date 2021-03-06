"""
Django settings for wsrc_site project.

For more information on this file, see
https://docs.djangoproject.com/en/1.6/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.6/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# Import sensitive settings not stored in this file
execfile(os.path.expanduser("~/etc/.wsrc-settings"))

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ]
        },
    }
]

# Application definition

INSTALLED_APPS = (
    'wsrc.site',
    'wsrc.site.accounts',
    'wsrc.site.usermodel',
    'wsrc.site.courts',
    'wsrc.site.competitions',
    'wsrc.site.email',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'rest_framework',
#    'debug_toolbar',
)

MIDDLEWARE = (
#    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'wsrc.site.navigation.NavigationMiddleWare',
    'wsrc.site.session_timeout.SessionTimeoutMiddleware',
)

ROOT_URLCONF = 'wsrc.site.settings.urls'

WSGI_APPLICATION = 'wsrc.site.settings.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    'default': _WSRC_SETTINGS["default_db"]
}

# Internationalization
# https://docs.djangoproject.com/en/1.6/topics/i18n/

LANGUAGE_CODE = 'en-GB'
DEFAULT_CHARSET = 'utf-8'

TIME_ZONE = 'Europe/London'
USE_I18N = True
USE_L10N = True
USE_TZ = True

AUTH_USER_MODEL = 'auth.User'
AUTH_PROFILE_MODULE = 'wsrc.site.usermodel.Player'

LOGIN_URL = '/login'
LOGOUT_URL = '/logout'
LOGIN_REDIRECT_URL = '/settings'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.6/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, "../../resources"),
    '/var/www/static',
)

INTERNAL_IPS = "127.0.0.1"

DEFAULT_FROM_EMAIL = "webmaster@wokingsquashclub.org"
SERVER_EMAIL       = "admin@wokingsquashclub.org"

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
    )
}


