from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from apps.keywords.models import Keyword, SearchResult, UploadFile
from apps.scraper.engine import scrape_bing, scrape_keyword_sync
from apps.scraper.resilience import MaxRetriesExceeded

from .fixtures import BING_HTML_NO_ADS, BING_HTML_WITH_ADS

User = get_user_model()


def _make_page_mock(html_content):
    page = MagicMock()
    page.goto.return_value = None
    page.wait_for_selector.return_value = None
    page.content.return_value = html_content
    return page


def _make_playwright_mock(html_content):
    page = _make_page_mock(html_content)
    context = MagicMock()
    context.new_page.return_value = page
    browser = MagicMock()
    browser.new_context.return_value = context
    browser.close.return_value = None
    pw = MagicMock()
    pw.chromium.launch.return_value = browser
    return pw


@pytest.fixture
def keyword_obj(db):
    user = User.objects.create_user('scrapeuser', 's@t.com', 'pass12345')
    upload = UploadFile.objects.create(user=user, file_name='t.csv', total_keywords=1)
    return Keyword.objects.create(upload_file=upload, text='python')


def test_scrape_bing_extracts_ads_and_links(monkeypatch):
    monkeypatch.setattr('apps.scraper.engine.time.sleep', lambda _: None)
    with patch('apps.scraper.engine.sync_playwright') as mock_pw_ctx:
        mock_pw_ctx.return_value.__enter__ = lambda s: _make_playwright_mock(BING_HTML_WITH_ADS)
        mock_pw_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result = scrape_bing('python')
    assert result['total_ads'] > 0
    assert result['total_links'] >= 5
    assert '<html>' in result['raw_html']


def test_scrape_bing_zero_ads_when_none(monkeypatch):
    monkeypatch.setattr('apps.scraper.engine.time.sleep', lambda _: None)
    with patch('apps.scraper.engine.sync_playwright') as mock_pw_ctx:
        mock_pw_ctx.return_value.__enter__ = lambda s: _make_playwright_mock(BING_HTML_NO_ADS)
        mock_pw_ctx.return_value.__exit__ = MagicMock(return_value=False)
        result = scrape_bing('obscure term')
    assert result['total_ads'] == 0
    assert result['total_links'] >= 3


@pytest.mark.django_db
def test_scrape_keyword_sync_sets_completed(keyword_obj, monkeypatch):
    monkeypatch.setattr('apps.scraper.engine.time.sleep', lambda _: None)
    with patch('apps.scraper.engine.sync_playwright') as mock_pw_ctx:
        mock_pw_ctx.return_value.__enter__ = lambda s: _make_playwright_mock(BING_HTML_WITH_ADS)
        mock_pw_ctx.return_value.__exit__ = MagicMock(return_value=False)
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
