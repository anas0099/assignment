import logging

logger = logging.getLogger(__name__)

CAPTCHA_SIGNALS = ['solve the challenge', 'captcha', 'are you a robot', 'unusual traffic']

LANGUAGE_SELECTION_SIGNALS = ['choose your language', 'one last step', 'select your language', 'select language']


class ScrapingError(Exception):
    pass


class MaxRetriesExceeded(ScrapingError):
    pass


class CaptchaDetected(ScrapingError):
    pass


def is_captcha_page(response_text):
    text_lower = response_text[:2000].lower()
    return any(signal in text_lower for signal in CAPTCHA_SIGNALS)


def is_language_selection_page(response_text):
    text_lower = response_text[:3000].lower()
    has_signal = any(signal in text_lower for signal in LANGUAGE_SELECTION_SIGNALS)
    has_results = 'b_results' in response_text
    return has_signal and not has_results
