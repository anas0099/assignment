import atexit
import json
import logging

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic
from decouple import config

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = config('KAFKA_BOOTSTRAP_SERVERS', default='localhost:9094')
KEYWORD_SCRAPE_TOPIC = 'keyword-scrape'
TOPIC_PARTITIONS = 18

KAFKA_SASL_USERNAME = config('KAFKA_SASL_USERNAME', default='')
KAFKA_SASL_PASSWORD = config('KAFKA_SASL_PASSWORD', default='')

_producer = None


def _kafka_conf(extra=None):
    conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    }
    if KAFKA_SASL_USERNAME and KAFKA_SASL_PASSWORD:
        conf.update({
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': KAFKA_SASL_USERNAME,
            'sasl.password': KAFKA_SASL_PASSWORD,
        })
    if extra:
        conf.update(extra)
    return conf


def get_producer():
    global _producer
    if _producer is None:
        _producer = Producer(_kafka_conf({'acks': 'all', 'retries': 3}))
        atexit.register(_shutdown_producer)
    return _producer


def _shutdown_producer():
    global _producer
    if _producer is not None:
        _producer.flush(timeout=5)
        _producer = None


def _delivery_callback(err, msg):
    if err:
        logger.error('Kafka delivery failed: %s', err)
    else:
        logger.info(
            'Kafka message delivered to %s [%d] @ %d',
            msg.topic(), msg.partition(), msg.offset(),
        )


def publish_keyword(keyword_id):
    producer = get_producer()
    payload = json.dumps({'keyword_id': keyword_id})
    producer.produce(
        KEYWORD_SCRAPE_TOPIC,
        value=payload.encode('utf-8'),
        key=str(keyword_id).encode('utf-8'),
        callback=_delivery_callback,
    )
    producer.poll(0)


def publish_keywords(keyword_ids):
    for kid in keyword_ids:
        publish_keyword(kid)
    get_producer().flush(timeout=10)


def ensure_topic():
    admin = AdminClient(_kafka_conf())
    topic = NewTopic(
        KEYWORD_SCRAPE_TOPIC,
        num_partitions=TOPIC_PARTITIONS,
        replication_factor=1,
    )
    futures = admin.create_topics([topic])
    for t, f in futures.items():
        try:
            f.result()
            logger.info('Created topic: %s', t)
        except Exception as e:
            if 'TopicExistsError' in str(type(e).__name__) or 'TOPIC_ALREADY_EXISTS' in str(e):
                logger.info('Topic already exists: %s', t)
            else:
                logger.error('Failed to create topic %s: %s', t, e)
