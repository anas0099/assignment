import dj_database_url
from decouple import config

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = [h.strip() for h in config('ALLOWED_HOSTS', default='').split(',') if h.strip()]

DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True,
    )
}

MIDDLEWARE = [
    'config.middleware.NonWWWRedirectMiddleware',
] + MIDDLEWARE  # noqa: F405

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
