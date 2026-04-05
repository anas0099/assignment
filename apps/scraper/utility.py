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

_driver_instance = None

CHROME_VERSION = 146


def _get_chrome_options(headless=True, block_images=True):
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
    return options


def get_driver(headless=True, block_images=True):
    global _driver_instance
    if _driver_instance is not None:
        try:
            _driver_instance.title
            return _driver_instance
        except Exception:
            _driver_instance = None

    options = _get_chrome_options(headless, block_images)
    _driver_instance = uc.Chrome(options=options, version_main=CHROME_VERSION)
    return _driver_instance


def close_driver():
    global _driver_instance
    if _driver_instance is not None:
        try:
            _driver_instance.quit()
        except Exception:
            pass
        _driver_instance = None


def wait_for_element(driver, css_selector, timeout=10):
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        return True
    except TimeoutException:
        return False


def scroll_to_bottom(driver):
    try:
        driver.execute_script(
            'if(document.body) window.scrollTo(0, document.body.scrollHeight)'
        )
    except WebDriverException:
        pass


def get_page_html(driver):
    return driver.page_source.replace('\x00', '')


def scrape_page(url, wait_selector='ol#b_results', wait_timeout=15, extra_wait=3,
                headless=True, block_images=True, max_retries=3):
    last_error = None

    for attempt in range(max_retries):
        try:
            driver = get_driver(headless, block_images)
            driver.get(url)
            time.sleep(2)

            found = wait_for_element(driver, wait_selector, timeout=wait_timeout)
            if not found:
                html = get_page_html(driver)
                if wait_selector.replace('#', '') in html:
                    logger.info('Selector found in HTML despite timeout — using page content')
                    scroll_to_bottom(driver)
                    time.sleep(extra_wait)
                    return html

                logger.warning(
                    'Selector %r not found, attempt %d/%d (url=%s, title=%s) — retrying',
                    wait_selector, attempt + 1, max_retries,
                    driver.current_url[:80], driver.title[:60],
                )
                last_error = TimeoutException(f'{wait_selector} not found')
                close_driver()
                time.sleep(3 + attempt * 2)
                continue

            scroll_to_bottom(driver)
            time.sleep(extra_wait)

            html = get_page_html(driver)
            return html

        except WebDriverException as err:
            logger.warning(
                'Browser error on attempt %d/%d: %s',
                attempt + 1, max_retries, err,
            )
            last_error = err
            close_driver()
            time.sleep(3 + attempt * 2)

    raise last_error or Exception(f'Failed after {max_retries} attempts')
