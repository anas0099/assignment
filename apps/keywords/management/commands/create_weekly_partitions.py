from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import connection

from apps.keywords.partitions import (
    PARTITIONED_TABLES,
    create_partition,
    drop_old_partitions,
)


class Command(BaseCommand):
    """Management command to pre-create weekly PostgreSQL partitions.

    Run this on every deploy to ensure partitions exist for the coming weeks.
    The --drop-old flag can be used to clean up partitions older than --keep-weeks,
    which is safe since dropping a partition is instant and lock-free.
    """
    help = 'Create PostgreSQL weekly partitions for Keyword and SearchResult tables'

    def add_arguments(self, parser):
        """Register --weeks-ahead, --drop-old, and --keep-weeks arguments."""
        parser.add_argument(
            '--weeks-ahead', type=int, default=4,
            help='How many future weeks to pre-create (default: 4)',
        )
        parser.add_argument(
            '--drop-old', action='store_true',
            help='Drop partitions older than --keep-weeks',
        )
        parser.add_argument(
            '--keep-weeks', type=int, default=8,
            help='Weeks of history to keep when using --drop-old (default: 8)',
        )

    def handle(self, *args, **options):
        """Create partitions for the current week through weeks_ahead future weeks."""
        weeks_ahead = options['weeks_ahead']
        today = date.today()

        with connection.cursor() as cursor:
            for i in range(weeks_ahead + 1):
                target = today + timedelta(weeks=i)
                for table in PARTITIONED_TABLES:
                    name = create_partition(cursor, table, target)
                    self.stdout.write(f'  Ensured partition {name}')

            if options['drop_old']:
                keep = options['keep_weeks']
                for table in PARTITIONED_TABLES:
                    dropped = drop_old_partitions(cursor, table, keep_weeks=keep)
                    for name in dropped:
                        self.stdout.write(self.style.WARNING(f'  Dropped old partition {name}'))

        self.stdout.write(self.style.SUCCESS('Weekly partitions up to date.'))
