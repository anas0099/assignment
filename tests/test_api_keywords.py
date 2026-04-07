from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.keywords.models import Keyword, SearchResult
from apps.keywords.services import create_keywords_from_list

User = get_user_model()


def _csv(content=b'python,django,flask'):
    return SimpleUploadedFile('k.csv', content, content_type='text/csv')


@pytest.mark.django_db
class TestKeywordUpload:
    @patch('apps.keywords.api.views.dispatch_scraping')
    def test_upload_creates_keywords(self, _, api_client):
        r = api_client.post('/api/keywords/upload/', {'file': _csv()}, format='multipart')
        assert r.status_code == 201
        assert r.data['keyword_count'] == 3
        assert Keyword.objects.filter(upload_file__user=api_client.user).count() == 3

    @patch('apps.keywords.api.views.dispatch_scraping')
    def test_upload_over_100_rejected(self, _, api_client):
        big = _csv(','.join(f'w{i}' for i in range(101)).encode())
        r = api_client.post('/api/keywords/upload/', {'file': big}, format='multipart')
        assert r.status_code == 400

    def test_upload_without_file_returns_400(self, api_client):
        r = api_client.post('/api/keywords/upload/', {}, format='multipart')
        assert r.status_code == 400

    def test_upload_requires_auth(self):
        from rest_framework.test import APIClient

        r = APIClient().post('/api/keywords/upload/', {'file': _csv()}, format='multipart')
        assert r.status_code == 401


@pytest.mark.django_db
class TestKeywordList:
    def test_returns_only_own_keywords(self, api_client, other_user):
        create_keywords_from_list(api_client.user, 'mine.csv', ['python'])
        create_keywords_from_list(other_user, 'theirs.csv', ['secret'])
        r = api_client.get('/api/keywords/')
        assert len(r.data) == 1
        assert r.data[0]['text'] == 'python'

    def test_status_filter(self, api_client):
        _, kws = create_keywords_from_list(api_client.user, 'f.csv', ['a', 'b'])
        kws[0].status = Keyword.Status.COMPLETED
        kws[0].save()
        r = api_client.get('/api/keywords/?status=completed')
        assert len(r.data) == 1

    def test_search_filter(self, api_client):
        create_keywords_from_list(api_client.user, 'f.csv', ['python', 'django'])
        r = api_client.get('/api/keywords/?q=pyth')
        assert len(r.data) == 1
        assert r.data[0]['text'] == 'python'


@pytest.mark.django_db
class TestKeywordDetail:
    def test_detail_includes_search_result(self, api_client):
        _, kws = create_keywords_from_list(api_client.user, 'f.csv', ['django'])
        kw = kws[0]
        SearchResult.objects.create(keyword=kw, total_ads=5, total_links=42)
        r = api_client.get(f'/api/keywords/{kw.id}/')
        assert r.status_code == 200
        assert r.data['search_result']['total_ads'] == 5

    def test_cannot_access_other_users_keyword(self, api_client, other_user):
        _, kws = create_keywords_from_list(other_user, 'f.csv', ['secret'])
        r = api_client.get(f'/api/keywords/{kws[0].id}/')
        assert r.status_code == 404


@pytest.mark.django_db
class TestKeywordStatus:
    def test_status_endpoint_returns_id_and_status(self, api_client):
        create_keywords_from_list(api_client.user, 'f.csv', ['kiwi', 'plum'])
        r = api_client.get('/api/keywords/status/')
        assert r.status_code == 200
        assert len(r.data) == 2
        assert all({'id', 'status'} <= set(item) for item in r.data)
