import pytest
from django.contrib.auth import get_user_model

from apps.keywords.models import Keyword, SearchResult, UploadFile

User = get_user_model()


@pytest.mark.django_db
class TestKeywordModel:
    def test_default_status_is_pending(self, user):
        upload = UploadFile.objects.create(user=user, file_name='f.csv', total_keywords=1)
        kw = Keyword.objects.create(upload_file=upload, text='python')
        assert kw.status == Keyword.Status.PENDING

    def test_default_retry_and_error_are_empty(self, user):
        upload = UploadFile.objects.create(user=user, file_name='f.csv', total_keywords=1)
        kw = Keyword.objects.create(upload_file=upload, text='python')
        assert kw.retry_count == 0
        assert kw.error_message == ''

    def test_user_property_returns_upload_owner(self, user):
        upload = UploadFile.objects.create(user=user, file_name='f.csv', total_keywords=1)
        kw = Keyword.objects.create(upload_file=upload, text='python')
        assert kw.user == user

    def test_cascade_delete_removes_keywords(self, user):
        upload = UploadFile.objects.create(user=user, file_name='f.csv', total_keywords=2)
        Keyword.objects.create(upload_file=upload, text='a')
        Keyword.objects.create(upload_file=upload, text='b')
        upload.delete()
        assert Keyword.objects.count() == 0


@pytest.mark.django_db
class TestSearchResultModel:
    def test_search_result_linked_to_keyword(self, user):
        upload = UploadFile.objects.create(user=user, file_name='f.csv', total_keywords=1)
        kw = Keyword.objects.create(upload_file=upload, text='django')
        sr = SearchResult.objects.create(keyword=kw, total_ads=3, total_links=20)
        assert kw.search_result == sr

    def test_cascade_delete_removes_result(self, user):
        upload = UploadFile.objects.create(user=user, file_name='f.csv', total_keywords=1)
        kw = Keyword.objects.create(upload_file=upload, text='django')
        SearchResult.objects.create(keyword=kw, total_ads=1, total_links=5)
        kw.delete()
        assert SearchResult.objects.count() == 0
