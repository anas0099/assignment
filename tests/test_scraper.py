from unittest.mock import MagicMock, patch

import pytest

from apps.scraper.resilience import (
    CaptchaDetected,
    MaxRetriesExceeded,
    is_captcha_page,
    is_language_selection_page,
)
from apps.scraper.engine import _parse_results


AD_HTML = '''
<html><body>
<ol id="b_results">
  <li class="b_ad"><a href="/ad1">Ad 1</a></li>
  <li><a href="/r1">Result 1</a></li>
  <li><a href="/r2">Result 2</a></li>
</ol>
</body></html>
'''

NO_AD_HTML = '''
<html><body>
<ol id="b_results">
  <li><a href="/r1">R1</a></li>
  <li><a href="/r2">R2</a></li>
</ol>
</body></html>
'''


class TestParseResults:
    def test_counts_ads_correctly(self):
        ads, links = _parse_results(AD_HTML)
        assert ads == 1
        assert links == 3

    def test_no_ads(self):
        ads, _ = _parse_results(NO_AD_HTML)
        assert ads == 0

    def test_no_results_container_counts_all_links(self):
        html = '<html><body><a href="/a">A</a><a href="/b">B</a></body></html>'
        _, links = _parse_results(html)
        assert links == 2

    def test_empty_html_returns_zeros(self):
        ads, links = _parse_results('<html></html>')
        assert ads == 0
        assert links == 0


class TestResilience:
    def test_captcha_page_detected(self):
        assert is_captcha_page('are you a robot? solve the challenge')

    def test_captcha_page_not_triggered_on_normal_page(self):
        assert not is_captcha_page('<html><body><ol id="b_results"></ol></body></html>')

    def test_language_selection_detected(self):
        assert is_language_selection_page('please select language for bing')

    def test_language_page_not_triggered_when_results_present(self):
        html = 'select language <ol id="b_results"><li>result</li></ol>'
        assert not is_language_selection_page(html)

    def test_normal_serp_is_not_language_page(self):
        assert not is_language_selection_page(AD_HTML)


@pytest.mark.django_db
class TestScrapeKeywordSync:
    @patch('apps.scraper.engine.scrape_bing')
    def test_completed_on_success(self, mock_scrape, user):
        from apps.keywords.models import Keyword, UploadFile
        from apps.scraper.engine import scrape_keyword_sync
        mock_scrape.return_value = {'total_ads': 2, 'total_links': 10, 'raw_html': '<html/>'}
        upload = UploadFile.objects.create(user=user, file_name='f.csv', total_keywords=1)
        kw = Keyword.objects.create(upload_file=upload, text='test')
        scrape_keyword_sync(kw.id)
        kw.refresh_from_db()
        assert kw.status == Keyword.Status.COMPLETED

    @patch('apps.scraper.engine.scrape_bing', side_effect=MaxRetriesExceeded('fail'))
    def test_failed_on_max_retries(self, _, user):
        from apps.keywords.models import Keyword, UploadFile
        from apps.scraper.engine import scrape_keyword_sync
        upload = UploadFile.objects.create(user=user, file_name='f.csv', total_keywords=1)
        kw = Keyword.objects.create(upload_file=upload, text='bad')
        scrape_keyword_sync(kw.id)
        kw.refresh_from_db()
        assert kw.status == Keyword.Status.FAILED
        assert kw.retry_count == 1
        assert 'fail' in kw.error_message
