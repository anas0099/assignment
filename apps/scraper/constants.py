BING_SEARCH_URL = 'https://www.bing.com/search'

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
]

AD_SELECTORS = [
    '.b_ad',
    '.sb_add',
    'li.b_ad',
    '.b_adLastChild',
    '#b_results > .b_ad',
    '.b_adTop',
    '.b_adBottom',
]

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 30

MAX_RETRIES = 5
BACKOFF_BASE = 2
BACKOFF_MAX = 32

RETRYABLE_STATUS_CODES = [429, 503]
