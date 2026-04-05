import logging
import random
import time

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from apps.keywords.models import Keyword, SearchResult

from .constants import AD_SELECTORS, BING_SEARCH_URL, USER_AGENTS
from .resilience import MaxRetriesExceeded, ScrapingError, is_captcha_page, is_language_selection_page

logger = logging.getLogger(__name__)

RESULTS_SELECTOR = 'ol#b_results'
PAGE_WAIT_MS = 15000
NAV_TIMEOUT_MS = 30000
REQUEST_DELAY_SECONDS = 3
MAX_SCRAPE_RETRIES = 3


def _random_ua():
    return random.choice(USER_AGENTS)


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
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=_random_ua(),
            locale='en-US',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
            },
        )
        page = context.new_page()
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)

        last_error = None
        for attempt in range(MAX_SCRAPE_RETRIES):
            try:
                page.goto('https://www.bing.com/', wait_until='load')
                time.sleep(1)

                search_url = (
                    f'{BING_SEARCH_URL}?q={keyword_text.replace(" ", "+")}'
                    f'&cc=US&setlang=en-US&mkt=en-US'
                )
                page.goto(search_url, wait_until='load')

                try:
                    page.wait_for_selector(RESULTS_SELECTOR, timeout=PAGE_WAIT_MS)
                except PlaywrightTimeout:
                    logger.warning(
                        'Results selector not found for %r, attempt %d/%d — retrying',
                        keyword_text, attempt + 1, MAX_SCRAPE_RETRIES,
                    )
                    last_error = ScrapingError(f'Results not rendered for {keyword_text!r}')
                    time.sleep(2 ** (attempt + 1))
                    continue

                page.wait_for_load_state('networkidle')

                raw_html = page.content().replace('\x00', '')

                if is_captcha_page(raw_html):
                    logger.warning('Captcha on attempt %d for %r', attempt + 1, keyword_text)
                    last_error = ScrapingError(f'Captcha for {keyword_text!r}')
                    time.sleep(2 ** (attempt + 1))
                    continue

                if is_language_selection_page(raw_html):
                    logger.warning('Language page on attempt %d for %r', attempt + 1, keyword_text)
                    last_error = ScrapingError(f'Language selection page for {keyword_text!r}')
                    time.sleep(2 ** (attempt + 1))
                    continue

                total_ads, total_links = _parse_results(raw_html)
                browser.close()
                return {
                    'total_ads': total_ads,
                    'total_links': total_links,
                    'raw_html': raw_html,
                }

            except PlaywrightTimeout as err:
                logger.warning(
                    'Navigation timeout on attempt %d for %r: %s',
                    attempt + 1, keyword_text, err,
                )
                last_error = err
                time.sleep(2 ** (attempt + 1))

        browser.close()
        raise MaxRetriesExceeded(
            f'Failed to scrape {keyword_text!r} after {MAX_SCRAPE_RETRIES} attempts: {last_error}'
        )


def scrape_keyword_sync(keyword_id):
    keyword = Keyword.objects.get(id=keyword_id)
    keyword.status = Keyword.Status.PROCESSING
    keyword.save(update_fields=['status', 'updated_at'])

    try:
        result = scrape_bing(keyword.text)
        SearchResult.objects.update_or_create(
            keyword=keyword,
            defaults=result,
        )
        keyword.status = Keyword.Status.COMPLETED
        keyword.save(update_fields=['status', 'updated_at'])
        time.sleep(REQUEST_DELAY_SECONDS)

    except MaxRetriesExceeded as err:
        keyword.status = Keyword.Status.FAILED
        keyword.retry_count = keyword.retry_count + 1
        keyword.save(update_fields=['status', 'retry_count', 'updated_at'])
        logger.error(
            'Scraping failed for keyword=%s id=%d retries=%d error=%s',
            keyword.text, keyword.id, keyword.retry_count, err,
        )

    except Exception as err:
        keyword.status = Keyword.Status.FAILED
        keyword.save(update_fields=['status', 'updated_at'])
        logger.error(
            'Unexpected error for keyword=%s id=%d error_type=%s error=%s',
            keyword.text, keyword.id, type(err).__name__, err,
        )
