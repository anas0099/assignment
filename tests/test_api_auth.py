import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.mark.django_db
class TestSignUp:
    def test_signup_creates_user_and_returns_token(self):
        client = APIClient()
        r = client.post('/api/auth/signup/', {'username': 'alice', 'password': 'strongpass1', 'email': 'a@a.com'})
        assert r.status_code == 201
        assert 'token' in r.data
        assert User.objects.filter(username='alice').exists()

    def test_signup_duplicate_username_fails(self):
        User.objects.create_user('bob', 'b@b.com', 'pass1234')
        client = APIClient()
        r = client.post('/api/auth/signup/', {'username': 'bob', 'password': 'pass1234'})
        assert r.status_code == 400


@pytest.mark.django_db
class TestLogin:
    def test_login_valid_credentials_returns_token(self):
        User.objects.create_user('carol', 'c@c.com', 'mypassword')
        client = APIClient()
        r = client.post('/api/auth/login/', {'username': 'carol', 'password': 'mypassword'})
        assert r.status_code == 200
        assert 'token' in r.data

    def test_login_wrong_password_returns_401(self):
        User.objects.create_user('dave', 'd@d.com', 'correct')
        client = APIClient()
        r = client.post('/api/auth/login/', {'username': 'dave', 'password': 'wrong'})
        assert r.status_code == 401

    def test_protected_endpoint_requires_token(self):
        client = APIClient()
        r = client.get('/api/keywords/')
        assert r.status_code == 401
