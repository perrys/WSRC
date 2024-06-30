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

SECRET_KEY = os.getenv('SECRET_KEY')

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

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Database
# https://docs.djangoproject.com/en/1.6/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'HOST': os.getenv('DB_HOST'),
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD')
    },
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

MEDIA_ROOT = os.getenv('MEDIA_ROOT')
MEDIA_URL = os.getenv('MEDIA_URL')
INTERNAL_IPS = "127.0.0.1"

DEFAULT_FROM_EMAIL = "webmaster@wokingsquashclub.org"
SERVER_EMAIL       = "admin@wokingsquashclub.org"

EMAIL_BACKEND       = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

EMAIL_HOST          = os.getenv('EMAIL_HOST')
EMAIL_HOST_USER     = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')

EMAIL_PORT          = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS       = True

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
    )
}

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
DEBUG = os.getenv("DEBUG") is not None
if DEBUG:  
  import urllib2
  try:
    sock = urllib2.urlopen("https://checkip.amazonaws.com/")
    my_ip = sock.read().strip()
    print "adding local IP " + str(my_ip)
    ALLOWED_HOSTS.append(my_ip)
  except Exception, ex:
    print str(ex)

BOOKING_SYSTEM_HMAC_KEY = os.getenv('BOOKING_SYSTEM_HMAC_KEY')
BOOKING_SYSTEM_RESOLUTION_MINS = int(os.getenv("BOOKING_SYSTEM_RESOLUTION_MINS"))
BOOKING_SYSTEM_STAGGER_SET = int(os.getenv("BOOKING_SYSTEM_STAGGER_SET"))
BOOKING_SYSTEM_STARTS_ENDS = [int(t) for t in os.getenv("BOOKING_SYSTEM_STARTS_ENDS").split(',')]
BOOKING_SYSTEM_CUTOFF_DAYS = int(os.getenv("BOOKING_SYSTEM_CUTOFF_DAYS"))
BOOKING_SYSTEM_REQUIRE_OPPONENT = bool(os.getenv("BOOKING_SYSTEM_REQUIRE_OPPONENT", "True"))
BOOKING_SYSTEM_ALLOW_BOOKING_SHORTCUT = False

