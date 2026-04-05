from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.keywords.models import Keyword, SearchResult
from apps.keywords.services import create_keywords_from_list

User = get_user_model()


@pytest.fixture
def api_client(db):
    user = User.objects.create_user('testuser', 'test@test.com', 'testpass123')
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    client.user = user
    return client


@pytest.mark.django_db
class TestKeywords:
    @patch('apps.keywords.api.views.dispatch_scraping')
    def test_upload_csv_creates_keywords(self, mock_dispatch, api_client):
        csv = SimpleUploadedFile('k.csv', b'python,django,flask', content_type='text/csv')
        response = api_client.post('/api/keywords/upload/', {'file': csv}, format='multipart')
        assert response.status_code == 201
        assert response.data['keyword_count'] == 3
        assert Keyword.objects.filter(upload_file__user=api_client.user).count() == 3
        assert mock_dispatch.called

    def test_list_returns_only_own_keywords(self, api_client):
        create_keywords_from_list(api_client.user, 'mine.csv', ['python'])
        other = User.objects.create_user('other', 'o@t.com', 'pass12345')
        create_keywords_from_list(other, 'theirs.csv', ['secret'])
        response = api_client.get('/api/keywords/')
        assert len(response.data) == 1
        assert response.data[0]['text'] == 'python'

    def test_detail_includes_search_result(self, api_client):
        _, keywords = create_keywords_from_list(api_client.user, 't.csv', ['django'])
        kw = keywords[0]
        SearchResult.objects.create(keyword=kw, total_ads=5, total_links=42, raw_html='<html></html>')
        response = api_client.get(f'/api/keywords/{kw.id}/')
        assert response.status_code == 200
        assert response.data['search_result']['total_ads'] == 5

    @patch('apps.keywords.api.views.dispatch_scraping')
    def test_upload_rejects_over_100_keywords(self, mock_dispatch, api_client):
        content = ','.join([f'w{i}' for i in range(101)])
        big = SimpleUploadedFile('big.csv', content.encode(), content_type='text/csv')
        response = api_client.post('/api/keywords/upload/', {'file': big}, format='multipart')
        assert response.status_code == 400
