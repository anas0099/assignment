from unittest.mock import patch

import pytest
from django.core.cache import cache

from apps.keywords.cache import (
    KEYWORD_LIST_TTL,
    SEARCH_RESULT_TTL,
    _user_cache_version,
    get_keyword_list,
    get_search_result,
    invalidate_search_result_cache,
    invalidate_user_keyword_cache,
    search_result_key,
    set_keyword_list,
    set_search_result,
)
from apps.scraper.rate_limiter import (
    MAX_REQUESTS_PER_WINDOW,
    RATE_LIMIT_KEY,
    acquire_scrape_slot,
)


class TestKeywordListCache:
    def test_cache_miss_returns_none(self):
        assert get_keyword_list(user_id=1, page=1) is None

    def test_cache_hit_returns_stored_data(self):
        data = ['kw1', 'kw2']
        set_keyword_list(user_id=1, page=1, data=data)
        assert get_keyword_list(user_id=1, page=1) == data

    def test_different_pages_stored_independently(self):
        set_keyword_list(user_id=1, page=1, data=['page1'])
        set_keyword_list(user_id=1, page=2, data=['page2'])
        assert get_keyword_list(user_id=1, page=1) == ['page1']
        assert get_keyword_list(user_id=1, page=2) == ['page2']

    def test_status_filter_stored_independently(self):
        set_keyword_list(user_id=1, page=1, data=['all'])
        set_keyword_list(user_id=1, page=1, data=['completed_only'], status='completed')
        assert get_keyword_list(user_id=1, page=1) == ['all']
        assert get_keyword_list(user_id=1, page=1, status='completed') == ['completed_only']

    def test_different_users_isolated(self):
        set_keyword_list(user_id=1, page=1, data=['user1'])
        set_keyword_list(user_id=2, page=1, data=['user2'])
        assert get_keyword_list(user_id=1, page=1) == ['user1']
        assert get_keyword_list(user_id=2, page=1) == ['user2']

    def test_invalidate_bumps_version_so_old_keys_miss(self):
        set_keyword_list(user_id=1, page=1, data=['before'])
        set_keyword_list(user_id=1, page=2, data=['before_p2'])

        version_before = _user_cache_version(user_id=1)
        invalidate_user_keyword_cache(user_id=1)
        version_after = _user_cache_version(user_id=1)

        assert version_after > version_before
        assert get_keyword_list(user_id=1, page=1) is None
        assert get_keyword_list(user_id=1, page=2) is None

    def test_invalidate_does_not_affect_other_users(self):
        set_keyword_list(user_id=1, page=1, data=['user1'])
        set_keyword_list(user_id=2, page=1, data=['user2'])

        invalidate_user_keyword_cache(user_id=1)

        assert get_keyword_list(user_id=1, page=1) is None
        assert get_keyword_list(user_id=2, page=1) == ['user2']

    def test_new_data_cached_after_invalidation(self):
        set_keyword_list(user_id=1, page=1, data=['old'])
        invalidate_user_keyword_cache(user_id=1)
        set_keyword_list(user_id=1, page=1, data=['new'])
        assert get_keyword_list(user_id=1, page=1) == ['new']


class TestSearchResultCache:
    def test_cache_miss_returns_none(self):
        assert get_search_result(keyword_id=99) is None

    def test_cache_hit_returns_stored_data(self):
        obj = {'total_ads': 3, 'total_links': 12}
        set_search_result(keyword_id=42, data=obj)
        assert get_search_result(keyword_id=42) == obj

    def test_cache_key_format(self):
        assert search_result_key(7) == 'search_result:7'

    def test_invalidate_removes_entry(self):
        set_search_result(keyword_id=5, data='result')
        invalidate_search_result_cache(keyword_id=5)
        assert get_search_result(keyword_id=5) is None

    def test_invalidate_does_not_affect_other_keywords(self):
        set_search_result(keyword_id=5, data='result_5')
        set_search_result(keyword_id=6, data='result_6')

        invalidate_search_result_cache(keyword_id=5)

        assert get_search_result(keyword_id=5) is None
        assert get_search_result(keyword_id=6) == 'result_6'


class TestRateLimiter:
    def test_first_request_always_allowed(self, locmem_cache):
        acquire_scrape_slot()
        assert locmem_cache.get(RATE_LIMIT_KEY) == 1

    def test_counter_increments_per_call(self, locmem_cache):
        for _ in range(5):
            acquire_scrape_slot()
        assert locmem_cache.get(RATE_LIMIT_KEY) == 5

    def test_blocks_when_limit_reached_then_proceeds(self):
        cache.set(RATE_LIMIT_KEY, MAX_REQUESTS_PER_WINDOW, 60)

        call_count = [0]

        def fake_current_count():
            call_count[0] += 1
            if call_count[0] == 1:
                return MAX_REQUESTS_PER_WINDOW
            return 0

        with patch('apps.scraper.rate_limiter.time.sleep') as mock_sleep, \
             patch('apps.scraper.rate_limiter._current_count', side_effect=fake_current_count):
            acquire_scrape_slot()
            mock_sleep.assert_called_once()

    def test_redis_error_allows_through(self):
        with patch('apps.scraper.rate_limiter._increment', return_value=0), \
             patch('apps.scraper.rate_limiter._current_count', return_value=0):
            acquire_scrape_slot()
