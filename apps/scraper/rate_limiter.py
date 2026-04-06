import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)

RATE_LIMIT_KEY = 'scraper:rate_limit'
MAX_REQUESTS_PER_WINDOW = 30
WINDOW_SECONDS = 60
POLL_INTERVAL_SECONDS = 2


def _current_count():
    return cache.get(RATE_LIMIT_KEY, 0)


def _increment():
    try:
        cache.add(RATE_LIMIT_KEY, 0, WINDOW_SECONDS)
        return cache.incr(RATE_LIMIT_KEY)
    except Exception as err:
        logger.warning('Rate limiter Redis error (allowing through): %s', err)
        return 0


def acquire_scrape_slot():
    while True:
        count = _current_count()
        if count < MAX_REQUESTS_PER_WINDOW:
            new_count = _increment()
            logger.debug('Rate limit slot acquired: %d/%d', new_count, MAX_REQUESTS_PER_WINDOW)
            return
        logger.info(
            'Rate limit reached (%d/%d), waiting %ds...',
            count, MAX_REQUESTS_PER_WINDOW, POLL_INTERVAL_SECONDS,
        )
        time.sleep(POLL_INTERVAL_SECONDS)
