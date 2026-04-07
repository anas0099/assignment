import dj_database_url
from decouple import config

from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = [
    h.strip() for h in config('ALLOWED_HOSTS', default='localhost,127.0.0.1,0.0.0.0').split(',') if h.strip()
]

DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default='postgres://bing_user:bing_pass@localhost:5433/bing_scraper')
    )
}
