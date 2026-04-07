import logging
import os
import threading
import time

import certifi
os.environ.setdefault('SSL_CERT_FILE', certifi.where())
os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())

from apps.scraper.resilience import MaxRetriesExceeded

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)

CHROME_VERSION = int(os.environ.get('CHROME_VERSION', '0')) or None
CHROME_BINARY = os.environ.get('CHROME_BINARY', '')
CHROMEDRIVER_PATH = os.environ.get('CHROMEDRIVER_PATH', '')
_driver_lock = threading.Lock()


def _create_driver(headless=True, block_images=True):
    options = uc.ChromeOptions()
    if CHROME_BINARY:
        options.binary_location = CHROME_BINARY
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--lang=en-US')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument(
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
    )
    if block_images:
        prefs = {
            'profile.managed_default_content_settings.images': 2,
            'profile.default_content_setting_values.notifications': 2,
        }
        options.add_experimental_option('prefs', prefs)
    driver_kwargs = {'options': options, 'version_main': CHROME_VERSION}
    if CHROMEDRIVER_PATH:
        driver_kwargs['driver_executable_path'] = CHROMEDRIVER_PATH
    with _driver_lock:
        driver = uc.Chrome(**driver_kwargs)
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        'userAgent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36'
        ),
    })
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def _safe_quit(driver):
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass


def _wait_for_element(driver, css_selector, timeout=15):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        return True
    except TimeoutException:
        return False


def _get_page_html(driver):
    return driver.page_source.replace('\x00', '')


def _has_search_results(html):
    return 'id="b_results"' in html or 'class="b_algo"' in html


def scrape_page(url, wait_timeout=15, extra_wait=3,
                headless=True, block_images=True, max_retries=3):
    last_error = None

    for attempt in range(max_retries):
        driver = None
        try:
            driver = _create_driver(headless, block_images)
            driver.get(url)
            time.sleep(2)

            found = _wait_for_element(driver, 'ol#b_results', timeout=wait_timeout)

            if not found:
                html = _get_page_html(driver)
                if _has_search_results(html):
                    logger.info(
                        'Results found in HTML despite selector timeout - using page content'
                    )
                    try:
                        driver.execute_script(
                            'if(document.body) window.scrollTo(0, document.body.scrollHeight)'
                        )
                    except WebDriverException:
                        pass
                    time.sleep(extra_wait)
                    _safe_quit(driver)
                    return html

                logger.warning(
                    'No results found, attempt %d/%d (url=%s, title=%s)',
                    attempt + 1, max_retries,
                    driver.current_url[:80], driver.title[:60],
                )
                last_error = TimeoutException('ol#b_results not found')
                _safe_quit(driver)
                time.sleep(3 + attempt * 2)
                continue

            try:
                driver.execute_script(
                    'if(document.body) window.scrollTo(0, document.body.scrollHeight)'
                )
            except WebDriverException:
                pass
            time.sleep(extra_wait)

            html = _get_page_html(driver)
            _safe_quit(driver)
            return html

        except Exception as err:
            logger.warning(
                'Browser error on attempt %d/%d: %s: %s',
                attempt + 1, max_retries, type(err).__name__, err,
            )
            last_error = err
            _safe_quit(driver)
            time.sleep(3 + attempt * 2)

    raise MaxRetriesExceeded(
        f'Scraping failed after {max_retries} attempts: {last_error}'
    ) from last_error
