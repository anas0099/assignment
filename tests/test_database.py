import pytest
from django.conf import settings
from django.db import connection


class TestDatabase:
    def test_backend_is_postgresql(self):
        assert 'postgresql' in settings.DATABASES['default']['ENGINE']

    @pytest.mark.django_db
    def test_connection_alive(self):
        connection.ensure_connection()
        assert connection.is_usable()

    @pytest.mark.django_db
    def test_core_tables_exist(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            tables = [r[0] for r in cursor.fetchall()]
        for t in ['auth_user', 'django_migrations', 'keywords_keyword']:
            assert t in tables

    @pytest.mark.django_db
    def test_no_pending_migrations(self):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('showmigrations', '--plan', stdout=out)
        unapplied = [line for line in out.getvalue().splitlines() if line.strip().startswith('[ ]')]
        assert unapplied == []
