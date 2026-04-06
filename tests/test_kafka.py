from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.keywords.models import Keyword, UploadFile
from apps.keywords.services import create_keywords_from_list, dispatch_scraping

User = get_user_model()


@pytest.mark.django_db
class TestDispatch:
    @patch('config.kafka.publish_keywords')
    def test_async_mode_publishes_to_kafka(self, mock_pub, settings, user):
        settings.SCRAPING_MODE = 'async'
        _, kws = create_keywords_from_list(user, 't.csv', ['a', 'b'])
        dispatch_scraping([k.id for k in kws])
        mock_pub.assert_called_once_with([k.id for k in kws])

    @patch('apps.scraper.engine.scrape_keyword_sync')
    def test_sync_mode_calls_scraper(self, mock_scrape, settings, user):
        settings.SCRAPING_MODE = 'sync'
        _, kws = create_keywords_from_list(user, 't.csv', ['cherry'])
        dispatch_scraping([kws[0].id])
        mock_scrape.assert_called_once_with(kws[0].id)

    @patch('config.kafka.publish_keywords')
    def test_async_upload_keywords_stay_pending(self, _, settings, api_client):
        from django.core.files.uploadedfile import SimpleUploadedFile
        settings.SCRAPING_MODE = 'async'
        csv = SimpleUploadedFile('k.csv', b'mango,grape', content_type='text/csv')
        api_client.post('/api/keywords/upload/', {'file': csv}, format='multipart')
        statuses = list(Keyword.objects.filter(
            upload_file__user=api_client.user,
        ).values_list('status', flat=True))
        assert all(s == Keyword.Status.PENDING for s in statuses)


@pytest.mark.django_db
class TestConsumerWorker:
    @patch('apps.scraper.engine.scrape_keyword_sync')
    def test_process_keyword_calls_sync_scraper(self, mock_sync, user):
        from kafka.consumer import _process_keyword
        upload = UploadFile.objects.create(user=user, file_name='t.csv', total_keywords=1)
        kw = Keyword.objects.create(upload_file=upload, text='peach')
        _process_keyword(kw.id)
        mock_sync.assert_called_once_with(kw.id)
