from unittest.mock import patch

import pytest

from apps.keywords.cache import (
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
    def test_miss_returns_none(self):
        assert get_keyword_list(1, 1) is None

    def test_hit_returns_data(self):
        set_keyword_list(1, 1, ['kw'])
        assert get_keyword_list(1, 1) == ['kw']

    def test_users_isolated(self):
        set_keyword_list(1, 1, ['u1'])
        set_keyword_list(2, 1, ['u2'])
        assert get_keyword_list(1, 1) == ['u1']
        assert get_keyword_list(2, 1) == ['u2']

    def test_status_filter_isolated(self):
        set_keyword_list(1, 1, ['all'])
        set_keyword_list(1, 1, ['done'], status='completed')
        assert get_keyword_list(1, 1) == ['all']
        assert get_keyword_list(1, 1, status='completed') == ['done']

    def test_invalidate_bumps_version(self):
        set_keyword_list(1, 1, ['old'])
        v = _user_cache_version(1)
        invalidate_user_keyword_cache(1)
        assert _user_cache_version(1) > v
        assert get_keyword_list(1, 1) is None

    def test_invalidate_does_not_affect_other_user(self):
        set_keyword_list(1, 1, ['u1'])
        set_keyword_list(2, 1, ['u2'])
        invalidate_user_keyword_cache(1)
        assert get_keyword_list(2, 1) == ['u2']


class TestSearchResultCache:
    def test_miss_returns_none(self):
        assert get_search_result(99) is None

    def test_hit_returns_data(self):
        set_search_result(42, {'ads': 3})
        assert get_search_result(42) == {'ads': 3}

    def test_key_format(self):
        assert search_result_key(7) == 'search_result:7'

    def test_invalidate_removes_entry(self):
        set_search_result(5, 'data')
        invalidate_search_result_cache(5)
        assert get_search_result(5) is None

    def test_invalidate_isolated(self):
        set_search_result(5, 'a')
        set_search_result(6, 'b')
        invalidate_search_result_cache(5)
        assert get_search_result(6) == 'b'


class TestRateLimiter:
    def test_first_request_increments_counter(self, locmem_cache):
        acquire_scrape_slot()
        assert locmem_cache.get(RATE_LIMIT_KEY) == 1

    def test_counter_accumulates(self, locmem_cache):
        for _ in range(5):
            acquire_scrape_slot()
        assert locmem_cache.get(RATE_LIMIT_KEY) == 5

    def test_blocks_then_proceeds_when_limit_reached(self):
        calls = [0]

        def fake_count():
            calls[0] += 1
            return MAX_REQUESTS_PER_WINDOW if calls[0] == 1 else 0

        with patch('apps.scraper.rate_limiter.time.sleep') as mock_sleep, \
             patch('apps.scraper.rate_limiter._current_count', side_effect=fake_count):
            acquire_scrape_slot()
            mock_sleep.assert_called_once()

    def test_redis_error_allows_through(self):
        with patch('apps.scraper.rate_limiter._increment', return_value=0), \
             patch('apps.scraper.rate_limiter._current_count', return_value=0):
            acquire_scrape_slot()
