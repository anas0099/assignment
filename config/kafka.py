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
    """Build a confluent-kafka config dict, adding SASL/SSL if credentials are set.

    When KAFKA_SASL_USERNAME and KAFKA_SASL_PASSWORD are empty (local Docker),
    returns a plain bootstrap config. In production (Confluent Cloud) the
    SASL_SSL block is added automatically.
    """
    conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    }
    if KAFKA_SASL_USERNAME and KAFKA_SASL_PASSWORD:
        conf.update(
            {
                'security.protocol': 'SASL_SSL',
                'sasl.mechanisms': 'PLAIN',
                'sasl.username': KAFKA_SASL_USERNAME,
                'sasl.password': KAFKA_SASL_PASSWORD,
            }
        )
    if extra:
        conf.update(extra)
    return conf


def get_producer():
    """Return the singleton Kafka producer, creating it on first call.

    The producer is flushed and cleaned up automatically on process exit
    via the atexit hook registered here.
    """
    global _producer
    if _producer is None:
        _producer = Producer(_kafka_conf({'acks': 'all', 'retries': 3}))
        atexit.register(_shutdown_producer)
    return _producer


def _shutdown_producer():
    """Flush any pending messages and release the producer on process exit."""
    global _producer
    if _producer is not None:
        _producer.flush(timeout=5)
        _producer = None


def _delivery_callback(err, msg):
    """Called by the producer after each message is acknowledged or fails.

    Logs delivery errors so failed publishes are visible in the logs even
    though the caller does not block waiting for confirmation.
    """
    if err:
        logger.error('Kafka delivery failed: %s', err)
    else:
        logger.info(
            'Kafka message delivered to %s [%d] @ %d',
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )


def publish_keyword(keyword_id):
    """Publish a single keyword ID as a JSON message to the scrape topic.

    The keyword ID is used as the message key so all messages for the same
    keyword always land on the same Kafka partition.
    """
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
    """Publish a batch of keyword IDs and flush the producer before returning.

    Flushing here ensures all messages are sent before the HTTP response is
    returned to the user, so the scraping starts immediately rather than
    waiting for the producer's internal queue to drain on its own.
    """
    for kid in keyword_ids:
        publish_keyword(kid)
    get_producer().flush(timeout=10)


def ensure_topic():
    """Create the scrape topic if it does not already exist.

    Safe to call on every startup - TopicExistsError is swallowed silently.
    The topic is created with TOPIC_PARTITIONS partitions so up to that many
    consumer processes can work in parallel.
    """
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
