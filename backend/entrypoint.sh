#!/bin/sh
set -e

if [ "${SKIP_MIGRATE:-0}" != "1" ]; then
    echo "Running database migrations..."
    python manage.py migrate --noinput
fi

if [ "${SKIP_COLLECTSTATIC:-0}" != "1" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

exec "$@"
