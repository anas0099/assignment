release: python manage.py migrate --noinput && python manage.py create_weekly_partitions --weeks-ahead 4
web: gunicorn config.wsgi --workers 2 --timeout 120 --bind 0.0.0.0:$PORT
worker: python kafka/consumer.py
