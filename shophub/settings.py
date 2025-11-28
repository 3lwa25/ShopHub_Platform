"""
Django settings for Shop Hub project.
"""

import os
from pathlib import Path

try:
    from decouple import config as decouple_config
except ImportError:
    decouple_config = None


def config(key, default=None, cast=None):
    """
    Lightweight substitute for python-decouple's config helper.
    Falls back to environment variables when python-decouple
    is not installed (e.g., on fresh dev setups).
    """
    if decouple_config is not None:
        kwargs = {'default': default}
        if cast is not None:
            kwargs['cast'] = cast
        return decouple_config(key, **kwargs)

    value = os.getenv(key, default)

    if value is None:
        return value

    if cast:
        try:
            if cast is bool:
                if isinstance(value, str):
                    return value.strip().lower() in ('1', 'true', 'yes', 'on')
                return bool(value)
            return cast(value)
        except (ValueError, TypeError):
            return default

    return value

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    # Django core apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    
    # Third-party apps
    'rest_framework',
    'rest_framework.authtoken',
    'rest_framework_simplejwt',
    'corsheaders',
    'phonenumber_field',
    
    # Shop Hub apps
    'apps.core',
    'apps.accounts',
    'apps.products',
    'apps.cart',
    'apps.orders',
    'apps.reviews',
    'apps.rewards',
    'apps.notifications',
    'apps.wishlist',
    'apps.analytics',
    'apps.ai_chatbot',
    'apps.virtual_tryon',
    
    # Optional packages (uncomment when installed):
    # 'admin_interface',
    # 'colorfield',
    # 'crispy_forms',
    # 'crispy_bootstrap5',
    # 'django_extensions',
    # 'import_export',
    # 'djmoney',
    # 'markdownx',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.common.middleware.GuestUserRestrictionMiddleware',
]

ROOT_URLCONF = 'shophub.urls'

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
                'apps.cart.context_processors.cart_context',
                'apps.accounts.context_processors.user_role_context',
                'apps.wishlist.context_processors.wishlist_context',
                'apps.rewards.context_processors.rewards_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'shophub.wsgi.application'

# Database - SQLite for Development (Switch to MySQL/PostgreSQL for Production)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Production Database (MySQL) - Uncomment for production
# DATABASES = {
#     'default': {
#         'ENGINE': config('DB_ENGINE', default='django.db.backends.mysql'),
#         'NAME': config('DB_NAME', default='shophub_db'),
#         'USER': config('DB_USER', default='root'),
#         'PASSWORD': config('DB_PASSWORD', default=''),
#         'HOST': config('DB_HOST', default='localhost'),
#         'PORT': config('DB_PORT', default='3306'),
#         'OPTIONS': {
#             'charset': 'utf8mb4',
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#         }
#     }
# }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = config('STATIC_URL', default='/static/')
STATIC_ROOT = BASE_DIR / config('STATIC_ROOT', default='staticfiles')
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# WhiteNoise static files storage
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files (User uploads)
MEDIA_URL = config('MEDIA_URL', default='/media/')
MEDIA_ROOT = BASE_DIR / config('MEDIA_ROOT', default='media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# JWT Settings
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Email configuration
# EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')
# EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
# EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
# EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
# EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
# EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
# DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@shophub.com')

# # Email Configuration - Gmail SMTP
DEFAULT_FROM_EMAIL = "shophub862@gmail.com"
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = "shophub862@gmail.com"
EMAIL_HOST_PASSWORD = "nvlnetvxjcyykbee"  # Gmail app password (no spaces)
EMAIL_USE_TLS = True
# Using Gmail SMTP backend - emails will be sent to actual recipients


# Default primary key field type

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Site Framework
SITE_ID = 1

# Session settings
SESSION_COOKIE_AGE = 86400 * 30  # 30 days
SESSION_SAVE_EVERY_REQUEST = False

# Security settings (Adjust for production)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# ================================
# AI Chatbot / Gemini Configuration
# ================================
# Your Gemini API Key
_DEFAULT_GEMINI_KEY = 'your gemini api key here'
GEMINI_API_KEY = config('GEMINI_API_KEY', default=_DEFAULT_GEMINI_KEY) or _DEFAULT_GEMINI_KEY

# Gemini Model Configuration
GEMINI_MODEL_NAME = config('GEMINI_MODEL_NAME', default='gemini-2.5-flash') or 'gemini-2.5-flash'
GEMINI_MAX_RETRIES = config('GEMINI_MAX_RETRIES', default=3, cast=int)
GEMINI_RETRY_BACKOFF_SECONDS = config('GEMINI_RETRY_BACKOFF_SECONDS', default=1.5, cast=float)
GEMINI_SAFETY_SETTINGS = None  # Can be overridden in environment or settings_local

# Chatbot Dataset Configuration (for product knowledge base)
CHATBOT_DATASET_ROOT = config(
    'CHATBOT_DATASET_ROOT',
    default=str(BASE_DIR / 'datasets' / 'product_knowledge')
)

# Virtual Try-On Settings
VTO_MAX_FILE_SIZE = config('VTO_MAX_FILE_SIZE', default=5242880, cast=int)  # 5MB
VTO_ALLOWED_FORMATS = config('VTO_ALLOWED_FORMATS', default='jpg,jpeg,png,webp').split(',')
VTO_PROCESSING_TIMEOUT = config('VTO_PROCESSING_TIMEOUT', default=30, cast=int)

# Rewards System
POINTS_PER_DOLLAR = config('POINTS_PER_DOLLAR', default=10, cast=int)
POINTS_TO_DOLLAR_RATIO = config('POINTS_TO_DOLLAR_RATIO', default=0.01, cast=float)
REFERRAL_BONUS_POINTS = config('REFERRAL_BONUS_POINTS', default=500, cast=int)
FIRST_ORDER_BONUS = config('FIRST_ORDER_BONUS', default=100, cast=int)

# Site Settings
SITE_NAME = config('SITE_NAME', default='Shop Hub')
SITE_URL = config('SITE_URL', default='http://localhost:8000')
SUPPORT_EMAIL = config('SUPPORT_EMAIL', default='support@shophub.com')
ADMIN_EMAIL = config('ADMIN_EMAIL', default='admin@shophub.com')

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# Pagination
PRODUCTS_PER_PAGE = 20
ORDERS_PER_PAGE = 10

# Cache (Optional - Redis)
if config('CACHE_ENABLED', default=False, cast=bool):
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            }
        }
    }

# Celery Configuration (Optional)
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Admin Interface Settings
X_FRAME_OPTIONS = 'SAMEORIGIN'
SILENCED_SYSTEM_CHECKS = ['security.W019']

# Phone Number Field
PHONENUMBER_DEFAULT_REGION = 'US'

# Money Field - EGP (Egyptian Pound)
CURRENCIES = ('EGP', 'USD', 'EUR')
CURRENCY_CHOICES = [
    ('EGP', 'Egyptian Pound'),
    ('USD', 'US Dollar'),
    ('EUR', 'Euro'),
]
DEFAULT_CURRENCY = 'EGP'

