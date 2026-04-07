"""
Shared rate limiter for the Bing scraper.

Uses a single Redis counter shared across all worker threads and processes.
The counter resets automatically after WINDOW_SECONDS via the Redis TTL.
"""

import logging
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)

RATE_LIMIT_KEY = 'scraper:rate_limit'
MAX_REQUESTS_PER_WINDOW = 30
WINDOW_SECONDS = 60
POLL_INTERVAL_SECONDS = 2


def _current_count():
    """Return the current number of requests made in the active window."""
    return cache.get(RATE_LIMIT_KEY, 0)


def _increment():
    """Atomically increment the counter, creating it if it doesn't exist yet.

    Uses cache.add to initialise the key only if absent, then incr to bump it.
    If Redis is unavailable the error is swallowed and 0 is returned so
    scraping continues rather than blocking indefinitely.
    """
    try:
        cache.add(RATE_LIMIT_KEY, 0, WINDOW_SECONDS)
        return cache.incr(RATE_LIMIT_KEY)
    except Exception as err:
        logger.warning('Rate limiter Redis error (allowing through): %s', err)
        return 0


def acquire_scrape_slot():
    """Block the calling thread until a scrape slot is available.

    Polls Redis every POLL_INTERVAL_SECONDS until the current window count
    is below the limit, then increments and returns. This keeps all workers
    combined under MAX_REQUESTS_PER_WINDOW requests per WINDOW_SECONDS.
    """
    while True:
        count = _current_count()
        if count < MAX_REQUESTS_PER_WINDOW:
            new_count = _increment()
            logger.debug('Rate limit slot acquired: %d/%d', new_count, MAX_REQUESTS_PER_WINDOW)
            return
        logger.info(
            'Rate limit reached (%d/%d), waiting %ds...',
            count,
            MAX_REQUESTS_PER_WINDOW,
            POLL_INTERVAL_SECONDS,
        )
        time.sleep(POLL_INTERVAL_SECONDS)
