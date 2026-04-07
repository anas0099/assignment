import json
import logging
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from confluent_kafka import Consumer, KafkaError
from config.kafka import KEYWORD_SCRAPE_TOPIC, _kafka_conf

logger = logging.getLogger(__name__)

running = True
MAX_WORKERS = int(os.environ.get('SCRAPER_WORKERS', '6'))
MAX_TOTAL_RETRIES = 5
SWEEP_INTERVAL_SECONDS = 30


def _backoff_seconds(retry_count):
    """Exponential backoff: 30s, 60s, 120s, 240s, 480s for retries 1-5."""
    return min(30 * (2 ** (retry_count - 1)), 480)


def _signal_handler(signum, frame):
    global running
    running = False
    logger.info('Shutdown signal received, closing consumer...')


def _process_keyword(keyword_id):
    from apps.scraper.engine import scrape_keyword_sync
    from apps.keywords.models import Keyword
    try:
        scrape_keyword_sync(keyword_id)
        kw = Keyword.objects.get(id=keyword_id)
        if kw.status == Keyword.Status.COMPLETED:
            logger.info('Scraped keyword_id=%d status=completed', keyword_id)
        else:
            logger.error(
                'Scraping failed keyword_id=%d attempt=%d/%d error=%s',
                keyword_id, kw.retry_count, MAX_TOTAL_RETRIES, kw.error_message[:120],
            )
    except Exception as err:
        logger.error(
            'Unhandled exception keyword_id=%d error_type=%s error=%s',
            keyword_id, type(err).__name__, err,
        )


def _sweep_failed_keywords():
    """
    Background thread that continuously re-queues failed keywords
    using exponential backoff. Runs every SWEEP_INTERVAL_SECONDS.

    Backoff schedule (by retry_count already recorded):
      retry 1 → wait  30s before next attempt
      retry 2 → wait  60s
      retry 3 → wait 120s
      retry 4 → wait 240s
      retry 5 → permanently failed (no more retries)
    """
    from django.utils import timezone
    from apps.keywords.models import Keyword
    from apps.keywords.services import _publish_to_kafka

    logger.info('Sweep thread started (interval=%ds, max_retries=%d)', SWEEP_INTERVAL_SECONDS, MAX_TOTAL_RETRIES)

    while running:
        time.sleep(SWEEP_INTERVAL_SECONDS)
        if not running:
            break

        try:
            now = timezone.now()
            candidates = Keyword.objects.filter(
                status=Keyword.Status.FAILED,
                retry_count__lt=MAX_TOTAL_RETRIES,
            )

            requeued = 0
            for kw in candidates:
                backoff = _backoff_seconds(kw.retry_count)
                elapsed = (now - kw.updated_at).total_seconds()

                if elapsed >= backoff:
                    kw.status = Keyword.Status.PENDING
                    kw.save(update_fields=['status', 'updated_at'])
                    try:
                        _publish_to_kafka(kw.id)
                        requeued += 1
                        logger.info(
                            'Sweep re-queued keyword_id=%d text=%r attempt=%d/%d (waited %.0fs / %ds backoff)',
                            kw.id, kw.text, kw.retry_count + 1, MAX_TOTAL_RETRIES, elapsed, backoff,
                        )
                    except Exception as pub_err:
                        kw.status = Keyword.Status.FAILED
                        kw.save(update_fields=['status', 'updated_at'])
                        logger.error('Sweep failed to publish keyword_id=%d: %s', kw.id, pub_err)

            if requeued:
                logger.info('Sweep cycle complete: re-queued %d keyword(s)', requeued)

        except Exception as err:
            logger.error('Sweep cycle error: %s: %s', type(err).__name__, err)


def run_consumer():
    global running

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    sweep_thread = threading.Thread(target=_sweep_failed_keywords, daemon=True, name='sweep')
    sweep_thread.start()

    consumer = Consumer(_kafka_conf({
        'group.id': 'scraper-workers',
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,
    }))

    consumer.subscribe([KEYWORD_SCRAPE_TOPIC])
    logger.info(
        'Kafka consumer started - topic=%s workers=%d max_retries=%d',
        KEYWORD_SCRAPE_TOPIC, MAX_WORKERS, MAX_TOTAL_RETRIES,
    )

    executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    try:
        while running:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error('Kafka consumer error: %s', msg.error())
                continue

            try:
                payload = json.loads(msg.value().decode('utf-8'))
                keyword_id = payload['keyword_id']
                logger.info('Consumed keyword_id=%d, submitting to worker pool', keyword_id)
                executor.submit(_process_keyword, keyword_id)
                consumer.commit(msg)
            except (json.JSONDecodeError, KeyError) as err:
                logger.error('Bad message payload: %s error=%s', msg.value(), err)
                consumer.commit(msg)

    finally:
        executor.shutdown(wait=True)
        consumer.close()
        logger.info('Kafka consumer closed.')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    )
    run_consumer()
