from unittest.mock import patch

import pytest
from django.core.cache.backends.locmem import LocMemCache


@pytest.fixture(autouse=True)
def locmem_cache():
    loc = LocMemCache('phase6_test', {})
    with patch('apps.keywords.cache.cache', loc), \
         patch('apps.scraper.rate_limiter.cache', loc):
        yield loc
    loc.clear()
