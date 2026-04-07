import logging
import os

logger = logging.getLogger(__name__)

MONITORING_ENABLED = os.environ.get('MONITORING_ENABLED', '').lower() == 'true'
MONITORING_DSN = os.environ.get('MONITORING_DSN', '')


def _send(event_type, payload):
    #TODO to add monitoring
    if not MONITORING_ENABLED or not MONITORING_DSN:
        return
    pass


def report_scrape_failure(keyword_id, keyword_text, error, retry_count, max_retries):
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
    logger.warning(
        'monitor:captcha_detected keyword_id=%d text=%r',
        keyword_id, keyword_text,
    )
    _send('captcha_detected', {
        'keyword_id': keyword_id,
        'keyword_text': keyword_text,
    })
