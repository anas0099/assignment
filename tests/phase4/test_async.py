from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.keywords.models import Keyword, UploadFile
from apps.keywords.services import create_keywords_from_list, dispatch_scraping

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user('asyncuser', 'a@t.com', 'pass12345')


@pytest.fixture
def api_client(user):
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    client.user = user
    return client


@pytest.mark.django_db
class TestKafkaPublish:
    @patch('config.kafka.publish_keywords')
    def test_async_mode_publishes_to_kafka(self, mock_publish, settings, user):
        settings.SCRAPING_MODE = 'async'
        _, keywords = create_keywords_from_list(user, 'test.csv', ['apple', 'banana'])
        keyword_ids = [k.id for k in keywords]
        dispatch_scraping(keyword_ids)
        mock_publish.assert_called_once_with(keyword_ids)

    @patch('apps.scraper.engine.scrape_keyword_sync')
    def test_sync_mode_calls_scraper_directly(self, mock_scrape, settings, user):
        settings.SCRAPING_MODE = 'sync'
        _, keywords = create_keywords_from_list(user, 'test.csv', ['cherry'])
        keyword_ids = [k.id for k in keywords]
        dispatch_scraping(keyword_ids)
        mock_scrape.assert_called_once_with(keywords[0].id)

    @patch('config.kafka.publish_keywords')
    def test_upload_returns_immediately_in_async_mode(self, mock_publish, settings, api_client):
        settings.SCRAPING_MODE = 'async'
        csv = SimpleUploadedFile('k.csv', b'mango,grape', content_type='text/csv')
        response = api_client.post('/api/keywords/upload/', {'file': csv}, format='multipart')
        assert response.status_code == 201
        assert response.data['keyword_count'] == 2
        assert Keyword.objects.filter(upload_file__user=api_client.user).count() == 2
        assert all(
            kw.status == Keyword.Status.PENDING
            for kw in Keyword.objects.filter(upload_file__user=api_client.user)
        )
        mock_publish.assert_called_once()


@pytest.mark.django_db
class TestKafkaConsumerWorker:
    @patch('apps.scraper.engine.scrape_keyword_sync')
    def test_process_keyword_calls_sync_scraper(self, mock_sync, user):
        from kafka.consumer import _process_keyword
        upload = UploadFile.objects.create(user=user, file_name='t.csv', total_keywords=1)
        kw = Keyword.objects.create(upload_file=upload, text='peach')
        _process_keyword(kw.id)
        mock_sync.assert_called_once_with(kw.id)


@pytest.mark.django_db
class TestStatusPolling:
    def test_status_endpoint_returns_keyword_statuses(self, api_client):
        create_keywords_from_list(api_client.user, 'f.csv', ['kiwi', 'plum'])
        response = api_client.get('/api/keywords/status/')
        assert response.status_code == 200
        assert len(response.data) == 2
        assert all('status' in item for item in response.data)
        assert all('id' in item for item in response.data)
