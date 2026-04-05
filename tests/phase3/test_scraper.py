from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from apps.keywords.models import Keyword, SearchResult, UploadFile
from apps.scraper.engine import _parse_results, scrape_keyword_sync
from apps.scraper.resilience import MaxRetriesExceeded

from tests.phase3.fixtures import BING_HTML_NO_ADS, BING_HTML_WITH_ADS

User = get_user_model()


@pytest.fixture
def keyword_obj(db):
    user = User.objects.create_user('scrapeuser', 's@t.com', 'pass12345')
    upload = UploadFile.objects.create(user=user, file_name='t.csv', total_keywords=1)
    return Keyword.objects.create(upload_file=upload, text='python')


def test_parse_results_extracts_ads_and_links():
    total_ads, total_links = _parse_results(BING_HTML_WITH_ADS)
    assert total_ads > 0
    assert total_links >= 5


def test_parse_results_zero_ads_when_none():
    total_ads, total_links = _parse_results(BING_HTML_NO_ADS)
    assert total_ads == 0
    assert total_links >= 3


@pytest.mark.django_db
def test_scrape_keyword_sync_sets_completed(keyword_obj, monkeypatch):
    monkeypatch.setattr('apps.scraper.engine.time.sleep', lambda _: None)
    mock_result = {
        'total_ads': 2,
        'total_links': 10,
        'raw_html': BING_HTML_WITH_ADS,
    }
    with patch('apps.scraper.engine.scrape_bing', return_value=mock_result):
        scrape_keyword_sync(keyword_obj.id)
    keyword_obj.refresh_from_db()
    assert keyword_obj.status == Keyword.Status.COMPLETED
    assert SearchResult.objects.filter(keyword=keyword_obj).exists()


@pytest.mark.django_db
def test_scrape_keyword_sync_sets_failed_after_retries(keyword_obj, monkeypatch):
    monkeypatch.setattr('apps.scraper.engine.time.sleep', lambda _: None)
    with patch('apps.scraper.engine.scrape_bing', side_effect=MaxRetriesExceeded('timeout')):
        scrape_keyword_sync(keyword_obj.id)
    keyword_obj.refresh_from_db()
    assert keyword_obj.status == Keyword.Status.FAILED
    assert keyword_obj.retry_count >= 1
