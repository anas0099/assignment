import json
import logging
import os
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.local')
django.setup()

from confluent_kafka import Consumer, KafkaError
from config.kafka import KAFKA_BOOTSTRAP_SERVERS, KEYWORD_SCRAPE_TOPIC

logger = logging.getLogger(__name__)

running = True
MAX_WORKERS = int(os.environ.get('SCRAPER_WORKERS', '6'))


def _signal_handler(signum, frame):
    global running
    running = False
    logger.info('Shutdown signal received, closing consumer...')


def _process_keyword(keyword_id):
    from apps.scraper.engine import scrape_keyword_sync
    try:
        scrape_keyword_sync(keyword_id)
        logger.info('Completed keyword_id=%d', keyword_id)
    except Exception as err:
        logger.error(
            'Failed keyword_id=%d error_type=%s error=%s',
            keyword_id, type(err).__name__, err,
        )


def run_consumer():
    global running

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    consumer = Consumer({
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': 'scraper-workers',
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,
    })

    consumer.subscribe([KEYWORD_SCRAPE_TOPIC])
    logger.info(
        'Kafka consumer started — topic=%s workers=%d',
        KEYWORD_SCRAPE_TOPIC, MAX_WORKERS,
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
