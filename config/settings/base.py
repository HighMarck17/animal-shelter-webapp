"""
Django base setttings - Common settings for all environments
"""
from pathlib import Path
from decouple import config as env_config

from config.shelter_config import SHELTER_CONFIG


# === SHELTER DOMAIN SETTINGS (branding/contacts, see config/shelter_config.py) ===
# A fork customizes these by editing config/shelter_config.py only. They are
# exposed to templates via apps.core.context_processor.site_config.
SHELTER_NAME = SHELTER_CONFIG['name']
SHELTER_TAGLINE = SHELTER_CONFIG['tagline']
CONTACT_PHONE = SHELTER_CONFIG['contact_phone']
PUBLIC_EMAIL = SHELTER_CONFIG['public_email']
ADDRESS_STREET_AND_NUMBER = SHELTER_CONFIG['address_street_and_number']
ADDRESS_CITY_AND_POSTAL_CODE = SHELTER_CONFIG['address_city_and_postal_code']
VISITING_HOURS_WEEKDAYS = SHELTER_CONFIG['visiting_hours_weekdays']
VISITING_HOURS_WEEKEND_SAT = SHELTER_CONFIG['visiting_hours_saturday']
VISITING_HOURS_WEEKEND_SUN = SHELTER_CONFIG['visiting_hours_sunday']


# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env_config('SECRET_KEY', default='django-insecure-CHANGE-ME-IN-PRODUCTION')

# === CUSTOM URLS ===
#  Admin URL
ADMIN_URL = env_config('ADMIN_URL', default='admin/')
#  API URLS
API_URL = env_config('API_URL', default='api/v1/')
API_SCHEMA_URL = env_config('API_SCHEMA_URL', default='api/schema/')
API_DOCS_URL = env_config('API_DOCS_URL', default='api/docs/')
API_REDOC_URL = env_config('API_REDOC_URL', default='api/redoc/')


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    
    # Third party apps
    'rest_framework',
    'django_filters',
    'corsheaders',
    'drf_spectacular',
    'django_recaptcha',  # django-recaptcha
    'axes',     # django-axes
    'widget_tweaks',
    
    # Local apps
    'apps.core',
    'apps.dogs',
    'apps.homepage',
    'apps.contacts',
    'apps.faq',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'apps.core.middleware.ResponseTimeMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.RequestLoggingMiddleware',
    'axes.middleware.AxesMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'apps.core.context_processor.site_config',  # Custom context processor (see apps/core/context_processor.py)
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
# UI strings use Italian as the source text (msgid). Set LANGUAGE_CODE to serve
# a different language and provide its catalog under locale/<lang>/ (an English
# example catalog ships in locale/en/).
LANGUAGE_CODE = 'it-it'
TIME_ZONE = 'Europe/Rome'
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / 'locale']

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# === CACHE CONFIGURATION ===
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'shelter-cache',
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}

# === SESSION SECURITY ===
SESSION_COOKIE_AGE = 3600  # 60 minutes
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_NAME = 'shelter_sessionid'

# Session backend (uses the cache)
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'

# === CLIENT IP (see apps/core/client_ip.py) ===
# request.META key holding the client address. Keep REMOTE_ADDR when Gunicorn
# faces clients directly; behind the bundled nginx, docker-compose.yml sets
# HTTP_X_REAL_IP. Never point it at a header clients can set themselves.
CLIENT_IP_META_KEY = env_config('CLIENT_IP_META_KEY', default='REMOTE_ADDR')

# === RATE LIMITING ===
RATELIMIT_ENABLE = True
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_VIEW = 'apps.core.views.rate_limit_view'
RATELIMIT_IP_META_KEY = 'apps.core.client_ip.get_client_ip'

# === GOOGLE RECAPTCHA ===
RECAPTCHA_PUBLIC_KEY = env_config('RECAPTCHA_PUBLIC_KEY', default='')
RECAPTCHA_PRIVATE_KEY = env_config('RECAPTCHA_PRIVATE_KEY', default='')
RECAPTCHA_REQUIRED_SCORE = 0.5

# Use reCAPTCHA TEST keys in development
if env_config('DJANGO_ENVIRONMENT', default='development') == 'development':
    SILENCED_SYSTEM_CHECKS = ['django_recaptcha.recaptcha_test_key_error']

# === DJANGO AXES (Brute Force Protection) ===
AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1
#AXES_LOCK_OUT_BY_COMBINATION_USER_AND_IP = True
AXES_LOCKOUT_PARAMETERS = ["ip_address", "username"]
AXES_RESET_ON_SUCCESS = True
AXES_CACHE = 'default'
AXES_CLIENT_IP_CALLABLE = 'apps.core.client_ip.get_client_ip'

# Authentication backend
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# === DJANGO REST FRAMEWORK ===
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'contact': '3/hour',
    },
}

# DRF Spectacular
SPECTACULAR_SETTINGS = {
    'TITLE': 'Shelter API',
    'DESCRIPTION': 'REST API for the animal shelter webapp',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# CORS
CORS_ALLOWED_ORIGINS = env_config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:8000'
).split(',')

# Security Settings Base
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True

# Email configuration
EMAIL_BACKEND = env_config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = env_config('EMAIL_HOST', default='smtp-relay.brevo.com')
EMAIL_PORT = env_config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = env_config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = env_config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env_config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env_config('DEFAULT_FROM_EMAIL', default='noreply@example.org')
# Staff address for contact-form notifications
STAFF_EMAIL = env_config('STAFF_EMAIL', default='staff@example.org')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 15,
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django.security': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'axes': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
