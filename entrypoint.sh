#!/bin/sh
set -e

echo "→ Migrazioni DB..."
python manage.py migrate --no-input

echo "→ collectstatic..."
python manage.py collectstatic --no-input

echo "→ Avvio Gunicorn..."
exec gunicorn config.wsgi:application -c gunicorn_config.py
