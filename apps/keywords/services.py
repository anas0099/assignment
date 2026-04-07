import logging

from .models import Keyword, UploadFile
from .parsers import get_parser

logger = logging.getLogger(__name__)


def parse_keywords_from_file(uploaded_file) -> list[str]:
    """Read an uploaded file and return a list of keyword strings.

    Delegates to the appropriate parser based on file extension.
    Seeks the file back to the start after reading so the caller can
    still access the raw bytes if needed.
    """
    parser = get_parser(uploaded_file.name)
    content = uploaded_file.read()
    uploaded_file.seek(0)
    return parser.parse(content)


def create_keywords_from_list(user, file_name, keyword_texts, file_hash=''):
    """Create an UploadFile record and all associated Keyword records in one go.

    Uses bulk_create for the keywords so a batch of 100 is a single INSERT
    rather than 100 individual ones.
    Returns the UploadFile instance and the list of created Keyword instances.
    """
    upload_file = UploadFile.objects.create(
        user=user,
        file_name=file_name,
        file_hash=file_hash,
        total_keywords=len(keyword_texts),
    )
    keywords = Keyword.objects.bulk_create([Keyword(upload_file=upload_file, text=text) for text in keyword_texts])
    return upload_file, keywords


def _publish_to_kafka(keyword_id):
    """Publish a single keyword ID to the Kafka topic for re-queuing."""
    from config.kafka import publish_keywords

    publish_keywords([keyword_id])


def dispatch_scraping(keyword_ids):
    """Send keyword IDs to be scraped, either via Kafka or inline depending on SCRAPING_MODE.

    In async mode (production) keywords are published to Kafka and a worker
    process picks them up. In sync mode (testing/development) each keyword is
    scraped immediately in the current process.
    """
    from django.conf import settings

    if settings.SCRAPING_MODE == 'async':
        from config.kafka import publish_keywords

        publish_keywords(keyword_ids)
        logger.info('Published %d keywords to Kafka', len(keyword_ids))
    else:
        from apps.scraper.engine import scrape_keyword_sync

        for keyword_id in keyword_ids:
            try:
                scrape_keyword_sync(keyword_id)
            except Exception as err:
                logger.error(
                    'Failed to scrape keyword_id=%d error_type=%s error=%s',
                    keyword_id,
                    type(err).__name__,
                    err,
                )
