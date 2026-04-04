import pytest
from django.conf import settings
from django.db import connection


class TestPostgresIntegration:
    def test_backend_is_postgresql(self):
        engine = settings.DATABASES['default']['ENGINE']
        assert engine == 'django.db.backends.postgresql'

    @pytest.mark.django_db
    def test_connection_is_alive(self):
        connection.ensure_connection()
        assert connection.is_usable()

    @pytest.mark.django_db
    def test_postgresql_version(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT version()')
            version = cursor.fetchone()[0]
        assert 'PostgreSQL' in version

    @pytest.mark.django_db
    def test_django_tables_exist(self):
        expected = ['auth_user', 'django_migrations', 'django_session']
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            )
            existing = [row[0] for row in cursor.fetchall()]
        for table in expected:
            assert table in existing, f'{table} not found'

    @pytest.mark.django_db
    def test_no_pending_migrations(self):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('showmigrations', '--plan', stdout=out)
        unapplied = [l for l in out.getvalue().splitlines() if l.strip().startswith('[ ]')]
        assert len(unapplied) == 0
