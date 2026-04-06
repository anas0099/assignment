import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

KEYWORD_LIST_TTL = 30
SEARCH_RESULT_TTL = 300


def _user_cache_version(user_id):
    key = f'keywords:user:{user_id}:version'
    cache.add(key, 1, timeout=None)
    return cache.get(key, 1)


def keyword_list_key(user_id, page, status=''):
    version = _user_cache_version(user_id)
    return f'keywords:user:{user_id}:v{version}:page:{page}:status:{status}'


def search_result_key(keyword_id):
    return f'search_result:{keyword_id}'


def get_keyword_list(user_id, page, status=''):
    return cache.get(keyword_list_key(user_id, page, status))


def set_keyword_list(user_id, page, data, status=''):
    cache.set(keyword_list_key(user_id, page, status), data, KEYWORD_LIST_TTL)


def get_search_result(keyword_id):
    return cache.get(search_result_key(keyword_id))


def set_search_result(keyword_id, data):
    cache.set(search_result_key(keyword_id), data, SEARCH_RESULT_TTL)


def invalidate_user_keyword_cache(user_id):
    try:
        version_key = f'keywords:user:{user_id}:version'
        cache.add(version_key, 0, timeout=None)
        cache.incr(version_key)
        logger.debug('Invalidated keyword list cache for user_id=%s', user_id)
    except Exception as err:
        logger.warning('Cache invalidation failed for user_id=%s: %s', user_id, err)


def invalidate_search_result_cache(keyword_id):
    try:
        cache.delete(search_result_key(keyword_id))
    except Exception as err:
        logger.warning('Cache invalidation failed for keyword_id=%s: %s', keyword_id, err)
