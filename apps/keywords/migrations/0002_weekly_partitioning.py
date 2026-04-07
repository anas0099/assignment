from datetime import date, timedelta

import django.db.models.deletion
from django.db import migrations, models


def _week_range(d):
    """Return (monday, next_monday) for the ISO week containing date d."""
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=7)


def _partition_suffix(d):
    """Return a partition name suffix like 2026_w15 for a given date."""
    year, week, _ = d.isocalendar()
    return f'{year}_w{week:02d}'


def convert_to_partitioned(apps, schema_editor):
    """Migrate the keyword and search result tables to range-partitioned versions.

    Backs up existing data, drops the original tables, recreates them as
    partitioned parent tables, creates a default partition and one for the
    current week, then restores all data from the backups.

    No-op on non-PostgreSQL backends (e.g. SQLite used in tests).
    """
    if schema_editor.connection.vendor != 'postgresql':
        return

    from django.db import connection

    today = date.today()
    start, end = _week_range(today)
    suffix = _partition_suffix(today)

    with connection.cursor() as cur:
        cur.execute('CREATE TABLE _kw_bak AS SELECT * FROM keywords_keyword')
        cur.execute('CREATE TABLE _sr_bak AS SELECT * FROM keywords_searchresult')

        cur.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM keywords_keyword')
        kw_next = cur.fetchone()[0]
        cur.execute('SELECT COALESCE(MAX(id), 0) + 1 FROM keywords_searchresult')
        sr_next = cur.fetchone()[0]

        cur.execute('DROP TABLE keywords_searchresult')
        cur.execute('DROP TABLE keywords_keyword')

        cur.execute(f"""
            CREATE TABLE keywords_keyword (
                id             bigint GENERATED ALWAYS AS IDENTITY (START WITH {kw_next}),
                upload_file_id bigint       NOT NULL,
                text           varchar(500) NOT NULL,
                status         varchar(20)  NOT NULL DEFAULT 'pending',
                retry_count    integer      NOT NULL DEFAULT 0,
                error_message  text         NOT NULL DEFAULT '',
                created_at     timestamptz  NOT NULL,
                updated_at     timestamptz  NOT NULL,
                PRIMARY KEY (id, created_at)
            ) PARTITION BY RANGE (created_at)
        """)

        cur.execute(f"""
            CREATE TABLE keywords_searchresult (
                id          bigint GENERATED ALWAYS AS IDENTITY (START WITH {sr_next}),
                keyword_id  bigint      NOT NULL,
                total_ads   integer     NOT NULL DEFAULT 0,
                total_links integer     NOT NULL DEFAULT 0,
                raw_html    text        NOT NULL DEFAULT '',
                scraped_at  timestamptz NOT NULL,
                PRIMARY KEY (id, scraped_at)
            ) PARTITION BY RANGE (scraped_at)
        """)

        cur.execute('CREATE TABLE keywords_keyword_default PARTITION OF keywords_keyword DEFAULT')
        cur.execute('CREATE TABLE keywords_searchresult_default PARTITION OF keywords_searchresult DEFAULT')

        cur.execute(f"""
            CREATE TABLE keywords_keyword_{suffix}
            PARTITION OF keywords_keyword
            FOR VALUES FROM ('{start}') TO ('{end}')
        """)
        cur.execute(f"""
            CREATE TABLE keywords_searchresult_{suffix}
            PARTITION OF keywords_searchresult
            FOR VALUES FROM ('{start}') TO ('{end}')
        """)

        cur.execute("""
            ALTER TABLE keywords_keyword
            ADD CONSTRAINT keywords_keyword_upload_file_id_fk
            FOREIGN KEY (upload_file_id) REFERENCES keywords_uploadfile(id)
            ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED
        """)

        cur.execute('CREATE INDEX ON keywords_keyword (upload_file_id)')
        cur.execute('CREATE INDEX ON keywords_keyword (status)')
        cur.execute('CREATE INDEX ON keywords_keyword (created_at)')
        cur.execute('CREATE INDEX ON keywords_searchresult (keyword_id)')
        cur.execute('CREATE INDEX ON keywords_searchresult (scraped_at)')

        cur.execute("""
            INSERT INTO keywords_keyword
                (id, upload_file_id, text, status, retry_count, error_message, created_at, updated_at)
            OVERRIDING SYSTEM VALUE
            SELECT id, upload_file_id, text, status, retry_count, error_message, created_at, updated_at
            FROM _kw_bak
        """)
        cur.execute("""
            INSERT INTO keywords_searchresult
                (id, keyword_id, total_ads, total_links, raw_html, scraped_at)
            OVERRIDING SYSTEM VALUE
            SELECT id, keyword_id, total_ads, total_links, raw_html, scraped_at
            FROM _sr_bak
        """)

        cur.execute('DROP TABLE _kw_bak')
        cur.execute('DROP TABLE _sr_bak')


def reverse_partitioned(apps, schema_editor):
    """Reversing this migration is not supported. Partitioned tables cannot be trivially reverted."""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('keywords', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='searchresult',
            name='keyword',
            field=models.OneToOneField(
                to='keywords.keyword',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='search_result',
                db_constraint=False,
            ),
        ),
        migrations.RunPython(convert_to_partitioned, reverse_partitioned),
    ]
