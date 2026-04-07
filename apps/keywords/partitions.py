from datetime import date, timedelta


def week_range(d: date):
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=7)


def partition_suffix(d: date):
    year, week, _ = d.isocalendar()
    return f'{year}_w{week:02d}'


PARTITIONED_TABLES = ['keywords_keyword', 'keywords_searchresult']


def create_partition(cursor, table, d: date):
    suffix = partition_suffix(d)
    name = f'{table}_{suffix}'
    start, end = week_range(d)
    cursor.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = '{name}' AND n.nspname = 'public'
            ) THEN
                EXECUTE 'CREATE TABLE {name}
                         PARTITION OF {table}
                         FOR VALUES FROM (''{start}'') TO (''{end}'')';
            END IF;
        END $$;
    """)
    return name


def list_partitions(cursor, table):
    cursor.execute("""
        SELECT c.relname
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_class p ON p.oid = i.inhparent
        WHERE p.relname = %s
        ORDER BY c.relname
    """, [table])
    return [row[0] for row in cursor.fetchall()]


def drop_old_partitions(cursor, table, keep_weeks=8):
    cutoff = date.today() - timedelta(weeks=keep_weeks)
    cutoff_suffix = partition_suffix(cutoff)
    dropped = []
    for name in list_partitions(cursor, table):
        if name == f'{table}_default':
            continue
        suffix = name.replace(f'{table}_', '')
        if suffix < cutoff_suffix:
            cursor.execute(f'DROP TABLE IF EXISTS {name}')
            dropped.append(name)
    return dropped
