import pytest
from django.contrib.auth import get_user_model
from django.test import Client
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


@pytest.mark.django_db
class TestLoginViewOpenRedirect:
    def test_safe_next_url_redirects_to_it(self):
        """A relative next URL on the same site is allowed after login."""
        User.objects.create_user('eve', 'e@e.com', 'pass1234')
        client = Client()
        r = client.post(
            '/accounts/login/?next=/keywords/',
            {'username': 'eve', 'password': 'pass1234'},
        )
        assert r.status_code == 302
        assert r['Location'] == '/keywords/'

    def test_external_next_url_redirects_to_dashboard(self):
        """An external next URL is rejected and falls back to the dashboard."""
        User.objects.create_user('frank', 'f@f.com', 'pass1234')
        client = Client()
        r = client.post(
            '/accounts/login/?next=https://evil.com',
            {'username': 'frank', 'password': 'pass1234'},
        )
        assert r.status_code == 302
        assert 'evil.com' not in r['Location']
