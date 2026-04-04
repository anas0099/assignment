from .base import *  # noqa: F401,F403

import dj_database_url
from decouple import config

DEBUG = True

DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default='postgres://bing_user:bing_pass@localhost:5433/bing_scraper')
    )
}
