import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache.backends.locmem import LocMemCache
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

fake_ck = ModuleType('confluent_kafka')
fake_ck.Producer = MagicMock
fake_ck.Consumer = MagicMock
fake_ck.KafkaError = type('KafkaError', (), {'_PARTITION_EOF': -191})
fake_admin = ModuleType('confluent_kafka.admin')
fake_admin.AdminClient = MagicMock
fake_admin.NewTopic = MagicMock
sys.modules.setdefault('confluent_kafka', fake_ck)
sys.modules.setdefault('confluent_kafka.admin', fake_admin)

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user('testuser', 'test@example.com', 'testpass123')


@pytest.fixture
def other_user(db):
    return User.objects.create_user('other', 'other@example.com', 'otherpass123')


@pytest.fixture
def api_client(user):
    client = APIClient()
    token, _ = Token.objects.get_or_create(user=user)
    client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    client.user = user
    return client


@pytest.fixture(autouse=True)
def locmem_cache():
    loc = LocMemCache('test', {})
    with patch('apps.keywords.cache.cache', loc), patch('apps.scraper.rate_limiter.cache', loc):
        yield loc
    loc.clear()
