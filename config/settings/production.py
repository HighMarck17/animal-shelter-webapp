"""
Production settings - With Security & Performance optimized for live environment
"""
from .base import *
from decouple import config as env_config

# Require a real SECRET_KEY in production: fail fast instead of falling back to
# the insecure development default defined in base.py.
SECRET_KEY = env_config('SECRET_KEY')

# === SECURITY WARNING: must be set to False in production! ===
DEBUG = env_config('DEBUG', default=False, cast=bool)
IS_LOCAL = env_config('IS_LOCAL', default=False, cast=bool)

ALLOWED_HOSTS = env_config('ALLOWED_HOSTS', default='').split(',')

# === Database - PostgreSQL for production ===
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env_config('DB_NAME'),
        'USER': env_config('DB_USER'),
        'PASSWORD': env_config('DB_PASSWORD'),
        'HOST': env_config('DB_HOST', default='localhost'),
        'PORT': env_config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# === CACHE WITH REDIS FOR PRODUCTION ===
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env_config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
    }
}

# === Security Settings ===
SECURE_SSL_REDIRECT = env_config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SESSION_COOKIE_SECURE = env_config('SESSION_COOKIE_SECURE', default=True, cast=bool)
CSRF_COOKIE_SECURE = env_config('CSRF_COOKIE_SECURE', default=True, cast=bool)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# === CSRF Settings ===
CSRF_TRUSTED_ORIGINS = env_config('CSRF_TRUSTED_ORIGINS', default='').split(',')

# === CORS Settings ===
CORS_ALLOWED_ORIGINS = env_config('CORS_ALLOWED_ORIGINS', default='').split(',')
CORS_ALLOW_CREDENTIALS = True

# === Storages: WhiteNoise for static files, local disk for media by default ===
# Django 5.1 removed the STATICFILES_STORAGE / DEFAULT_FILE_STORAGE settings:
# they are silently ignored, so storages must be configured here.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# === CLOUDINARY for media files (apps/core/storage.py) ===
if not IS_LOCAL:
    CLOUDINARY_STORAGE = {
        'CLOUD_NAME': env_config('CLOUDINARY_CLOUD_NAME'),
        'API_KEY': env_config('CLOUDINARY_API_KEY'),
        'API_SECRET': env_config('CLOUDINARY_API_SECRET'),
    }

    STORAGES['default'] = {
        'BACKEND': 'apps.core.storage.CloudinaryMediaStorage',
    }

# === Email - Production SMTP ===
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env_config('EMAIL_HOST')
EMAIL_PORT = env_config('EMAIL_PORT', cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env_config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = env_config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = env_config('DEFAULT_FROM_EMAIL')
STAFF_EMAIL = env_config('STAFF_EMAIL', default=DEFAULT_FROM_EMAIL)

# Logging for production
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'production.log',
            'maxBytes': 1024 * 1024 * 15,
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file', 'mail_admins'],
            'level': 'WARNING',
            'propagate': True,
        },
        'django.security': {
            'handlers': ['console', 'file', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Admin URL custom
ADMIN_URL = env_config('ADMIN_URL', default='admin/')

# Admins
_admin_email = env_config('ADMIN_EMAIL', default='')
ADMINS = [('Admin', _admin_email)] if _admin_email else []
MANAGERS = ADMINS
