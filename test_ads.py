import sys
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')

import django
django.setup()

from apps.scraper.utility import scrape_page
from apps.scraper.engine import _parse_results, WAIT_TIMEOUT, EXTRA_RENDER_WAIT
from apps.scraper.constants import AD_SELECTORS, BING_SEARCH_URL
from apps.scraper.resilience import is_captcha_page, is_language_selection_page
from bs4 import BeautifulSoup

keyword = ' '.join(sys.argv[1:]) or 'car insurance'
url = f'{BING_SEARCH_URL}?q={keyword.replace(" ", "+")}&cc=US&setlang=en-US&mkt=en-US'

print(f'Keyword  : {keyword}')
print(f'URL      : {url}')
print(f'Waiting  : {WAIT_TIMEOUT}s timeout + {EXTRA_RENDER_WAIT}s extra render wait')
print()

html = scrape_page(url, wait_timeout=WAIT_TIMEOUT, extra_wait=EXTRA_RENDER_WAIT)

print(f'HTML size: {len(html):,} bytes')
print(f'Captcha  : {is_captcha_page(html)}')
print(f'LangPage : {is_language_selection_page(html)}')
print()

soup = BeautifulSoup(html, 'html.parser')

print('=== AD SELECTORS ===')
seen = set()
total_ads = 0
for sel in AD_SELECTORS:
    elements = soup.select(sel)
    unique = [e for e in elements if id(e) not in seen]
    for e in unique:
        seen.add(id(e))
    total_ads += len(unique)
    marker = '<-- found' if unique else ''
    print(f'  {sel:40}  {len(unique):>3} {marker}')

print()
print(f'total_ads   = {total_ads}')

container = soup.find('ol', id='b_results')
if container:
    total_links = len(container.find_all('a', href=True))
else:
    total_links = len(soup.find_all('a', href=True))

print(f'total_links = {total_links}')

print()
print('=== b_ads_magazine_container ===')
div = soup.find(id='b_ads_magazine_container')
if div:
    inner = str(div)
    print(f'Present  : yes ({len(inner)} chars)')
    print(f'Has kids : {len(list(div.children))} children')
    if len(inner) > 50:
        print(f'Preview  : {inner[:400]}')
    else:
        print('Empty (Bing withheld ads - typical for datacenter/Docker IPs)')
else:
    print('Not found in HTML')

print()
print('=== li classes in #b_results ===')
if container:
    for li in container.find_all('li', recursive=False):
        classes = li.get('class', [])
        print(' ', classes)
