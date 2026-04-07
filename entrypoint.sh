set -e

echo "Waiting for Postgres..."
while ! python3 -c "
import dj_database_url, psycopg, os
db = dj_database_url.config(default=os.environ.get('DATABASE_URL'))
psycopg.connect(
    host=db['HOST'], port=db['PORT'],
    user=db['USER'], password=db['PASSWORD'],
    dbname=db['NAME']
).close()
" 2>/dev/null; do
    sleep 1
done
echo "Postgres ready."

echo "Running migrations..."
python3 manage.py migrate --noinput

echo "Creating weekly partitions..."
python3 manage.py create_weekly_partitions --weeks-ahead 4

echo "Collecting static files..."
python3 manage.py collectstatic --noinput 2>/dev/null || true

echo "Starting gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
