"""
Redis caching helpers for keyword lists and search results.

Keyword list cache uses a version counter per user. Calling
invalidate_user_keyword_cache bumps the version, which makes all
existing list cache keys stale without needing to enumerate or
delete them individually.

Search result cache is a simple key-per-keyword with a fixed TTL.
"""
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

KEYWORD_LIST_TTL = 30
SEARCH_RESULT_TTL = 300


def _user_cache_version(user_id):
    """Return the current cache version for a user's keyword list.

    The version is stored indefinitely. cache.add only sets it if the key
    does not already exist, so the first call initialises it to 1.
    """
    key = f'keywords:user:{user_id}:version'
    cache.add(key, 1, timeout=None)
    return cache.get(key, 1)


def keyword_list_key(user_id, page, status=''):
    """Build a versioned cache key for a user's keyword list page."""
    version = _user_cache_version(user_id)
    return f'keywords:user:{user_id}:v{version}:page:{page}:status:{status}'


def search_result_key(keyword_id):
    """Build the cache key for a single keyword's search result."""
    return f'search_result:{keyword_id}'


def get_keyword_list(user_id, page, status=''):
    """Return a cached keyword list page for a user, or None on a cache miss."""
    return cache.get(keyword_list_key(user_id, page, status))


def set_keyword_list(user_id, page, data, status=''):
    """Cache a keyword list page for a user with a short TTL."""
    cache.set(keyword_list_key(user_id, page, status), data, KEYWORD_LIST_TTL)


def get_search_result(keyword_id):
    """Return the cached search result for a keyword, or None on a miss."""
    return cache.get(search_result_key(keyword_id))


def set_search_result(keyword_id, data):
    """Cache a keyword's search result. Results don't change once scraped so a longer TTL is fine."""
    cache.set(search_result_key(keyword_id), data, SEARCH_RESULT_TTL)


def invalidate_user_keyword_cache(user_id):
    """Invalidate all cached keyword list pages for a user.

    Bumps the version counter so every existing list key becomes a cache
    miss on the next read, without needing to track or delete individual keys.
    """
    try:
        version_key = f'keywords:user:{user_id}:version'
        cache.add(version_key, 0, timeout=None)
        cache.incr(version_key)
        logger.debug('Invalidated keyword list cache for user_id=%s', user_id)
    except Exception as err:
        logger.warning('Cache invalidation failed for user_id=%s: %s', user_id, err)


def invalidate_search_result_cache(keyword_id):
    """Delete the cached search result for a specific keyword."""
    try:
        cache.delete(search_result_key(keyword_id))
    except Exception as err:
        logger.warning('Cache invalidation failed for keyword_id=%s: %s', keyword_id, err)
