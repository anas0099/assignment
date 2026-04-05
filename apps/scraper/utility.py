import logging
import os
import time

import certifi
os.environ.setdefault('SSL_CERT_FILE', certifi.where())
os.environ.setdefault('REQUESTS_CA_BUNDLE', certifi.where())

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)

CHROME_VERSION = 146


def _create_driver(headless=True, block_images=True):
    options = uc.ChromeOptions()
    if headless:
        options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--lang=en-US')
    if block_images:
        prefs = {
            'profile.managed_default_content_settings.images': 2,
            'profile.default_content_setting_values.notifications': 2,
        }
        options.add_experimental_option('prefs', prefs)
    return uc.Chrome(options=options, version_main=CHROME_VERSION)


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
                        'Results found in HTML despite selector timeout — using page content'
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

        except WebDriverException as err:
            logger.warning(
                'Browser error on attempt %d/%d: %s',
                attempt + 1, max_retries, err,
            )
            last_error = err
            _safe_quit(driver)
            time.sleep(3 + attempt * 2)

    raise last_error or Exception(f'Failed after {max_retries} attempts')
