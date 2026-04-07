"""
Monitoring hooks for scraping failures.

All functions here are safe to call unconditionally. When MONITORING_ENABLED
is not set they only log and return immediately. To wire up a real monitoring
service (e.g. Sentry), set MONITORING_ENABLED=true and MONITORING_DSN, then
fill in the _send function body.
"""
import logging
import os

logger = logging.getLogger(__name__)

MONITORING_ENABLED = os.environ.get('MONITORING_ENABLED', '').lower() == 'true'
MONITORING_DSN = os.environ.get('MONITORING_DSN', '')


def _send(event_type, payload):
    """Forward an event to the external monitoring service.

    Currently a stub. Set MONITORING_ENABLED=true and MONITORING_DSN,
    then add the integration (e.g. sentry_sdk.capture_message) here.
    """
    if not MONITORING_ENABLED or not MONITORING_DSN:
        return
    pass


def report_scrape_failure(keyword_id, keyword_text, error, retry_count, max_retries):
    """Log and report a single scrape failure. Called on every failed attempt."""
    logger.warning(
        'monitor:scrape_failure keyword_id=%d text=%r retry=%d/%d error=%s',
        keyword_id, keyword_text, retry_count, max_retries, error,
    )
    _send('scrape_failure', {
        'keyword_id': keyword_id,
        'keyword_text': keyword_text,
        'error': str(error),
        'retry_count': retry_count,
        'max_retries': max_retries,
    })


def report_permanent_failure(keyword_id, keyword_text, error):
    """Log and report a keyword that has exhausted all retry attempts."""
    logger.error(
        'monitor:permanent_failure keyword_id=%d text=%r error=%s',
        keyword_id, keyword_text, error,
    )
    _send('permanent_failure', {
        'keyword_id': keyword_id,
        'keyword_text': keyword_text,
        'error': str(error),
    })


def report_captcha_detected(keyword_id, keyword_text):
    """Log and report when Bing served a captcha instead of results."""
    logger.warning(
        'monitor:captcha_detected keyword_id=%d text=%r',
        keyword_id, keyword_text,
    )
    _send('captcha_detected', {
        'keyword_id': keyword_id,
        'keyword_text': keyword_text,
    })
