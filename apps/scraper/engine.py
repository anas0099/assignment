import logging
import time

from bs4 import BeautifulSoup

from apps.keywords.models import Keyword, SearchResult

from .constants import AD_SELECTORS, BING_SEARCH_URL
from .monitoring import report_permanent_failure, report_scrape_failure
from .resilience import MaxRetriesExceeded, ScrapingError, is_captcha_page, is_language_selection_page
from .utility import scrape_page

logger = logging.getLogger(__name__)

REQUEST_DELAY_SECONDS = 1
MAX_SCRAPE_RETRIES = 2
MAX_TOTAL_RETRIES = 5
WAIT_TIMEOUT = 12
EXTRA_RENDER_WAIT = 3


def _parse_results(raw_html):
    soup = BeautifulSoup(raw_html, 'html.parser')

    total_ads = 0
    seen = set()
    for selector in AD_SELECTORS:
        for el in soup.select(selector):
            el_id = id(el)
            if el_id not in seen:
                seen.add(el_id)
                total_ads += 1

    results_container = soup.find('ol', id='b_results')
    if results_container:
        total_links = len(results_container.find_all('a', href=True))
    else:
        total_links = len(soup.find_all('a', href=True))

    return total_ads, total_links


def scrape_bing(keyword_text):
    search_url = (
        f'{BING_SEARCH_URL}?q={keyword_text.replace(" ", "+")}'
        f'&cc=US&setlang=en-US&mkt=en-US'
    )

    raw_html = scrape_page(
        url=search_url,
        wait_timeout=WAIT_TIMEOUT,
        extra_wait=EXTRA_RENDER_WAIT,
        max_retries=MAX_SCRAPE_RETRIES,
    )

    if is_captcha_page(raw_html):
        raise ScrapingError(f'Captcha page for {keyword_text!r}')

    if is_language_selection_page(raw_html):
        raise ScrapingError(f'Language selection page for {keyword_text!r}')

    total_ads, total_links = _parse_results(raw_html)

    return {
        'total_ads': total_ads,
        'total_links': total_links,
        'raw_html': raw_html,
    }


def scrape_keyword_sync(keyword_id):
    from apps.keywords.cache import (
        invalidate_search_result_cache,
        invalidate_user_keyword_cache,
        set_search_result,
    )
    from apps.scraper.rate_limiter import acquire_scrape_slot

    keyword = Keyword.objects.select_related('upload_file').get(id=keyword_id)
    user_id = keyword.upload_file.user_id

    keyword.status = Keyword.Status.PROCESSING
    keyword.save(update_fields=['status', 'updated_at'])

    try:
        acquire_scrape_slot()
        result = scrape_bing(keyword.text)
        SearchResult.objects.update_or_create(
            keyword=keyword,
            defaults=result,
        )
        keyword.status = Keyword.Status.COMPLETED
        keyword.error_message = ''
        keyword.save(update_fields=['status', 'error_message', 'updated_at'])

        keyword.refresh_from_db()
        set_search_result(keyword.id, keyword)
        invalidate_user_keyword_cache(user_id)

        time.sleep(REQUEST_DELAY_SECONDS)

    except (MaxRetriesExceeded, ScrapingError) as err:
        keyword.retry_count += 1
        keyword.status = Keyword.Status.FAILED
        keyword.error_message = str(err)
        keyword.save(update_fields=['status', 'retry_count', 'error_message', 'updated_at'])
        invalidate_search_result_cache(keyword.id)
        invalidate_user_keyword_cache(user_id)
        logger.error(
            'Scraping failed keyword=%r id=%d attempt=%d/%d error=%s',
            keyword.text, keyword.id, keyword.retry_count, MAX_TOTAL_RETRIES,
            keyword.error_message[:120],
        )
        report_scrape_failure(keyword.id, keyword.text, err, keyword.retry_count, MAX_TOTAL_RETRIES)
        if keyword.retry_count >= MAX_TOTAL_RETRIES:
            report_permanent_failure(keyword.id, keyword.text, err)

    except Exception as err:
        keyword.retry_count += 1
        keyword.status = Keyword.Status.FAILED
        keyword.error_message = f'{type(err).__name__}: {err}'
        keyword.save(update_fields=['status', 'retry_count', 'error_message', 'updated_at'])
        invalidate_search_result_cache(keyword.id)
        invalidate_user_keyword_cache(user_id)
        logger.error(
            'Unexpected error keyword=%r id=%d error_type=%s error=%s',
            keyword.text, keyword.id, type(err).__name__, err,
        )
        report_scrape_failure(keyword.id, keyword.text, err, keyword.retry_count, MAX_TOTAL_RETRIES)
        if keyword.retry_count >= MAX_TOTAL_RETRIES:
            report_permanent_failure(keyword.id, keyword.text, err)
