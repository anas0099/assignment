"""
Exceptions and page-detection helpers for the Bing scraper.

Keeps error types and detection logic separate from the scraping
mechanics so each can be tested in isolation.
"""

import logging

logger = logging.getLogger(__name__)

CAPTCHA_SIGNALS = ['solve the challenge', 'captcha', 'are you a robot', 'unusual traffic']

LANGUAGE_SELECTION_SIGNALS = ['choose your language', 'one last step', 'select your language', 'select language']


class ScrapingError(Exception):
    """Raised when a page is successfully loaded but its content is unusable."""


class MaxRetriesExceeded(ScrapingError):
    """Raised when all retry attempts for a page are exhausted."""


class CaptchaDetected(ScrapingError):
    """Raised when Bing returns a challenge page instead of results."""


def is_captcha_page(response_text):
    """Return True if the page looks like a Bing captcha or bot challenge.

    Only checks the first 2000 characters since the challenge banner
    always appears near the top of the document.
    """
    text_lower = response_text[:2000].lower()
    return any(signal in text_lower for signal in CAPTCHA_SIGNALS)


def is_language_selection_page(response_text):
    """Return True if Bing is showing a language/region selection screen.

    Requires both a matching signal phrase AND the absence of the results
    container, because language-related strings can appear in normal result
    pages (e.g. setlang in URLs) without it being a selection interstitial.
    """
    text_lower = response_text[:3000].lower()
    has_signal = any(signal in text_lower for signal in LANGUAGE_SELECTION_SIGNALS)
    has_results = 'b_results' in response_text
    return has_signal and not has_results
