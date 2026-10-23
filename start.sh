#!/usr/bin/env bash

set -euo pipefail

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.prod}"

: "${REDIS_URL:?REDIS_URL environment variable is required}"
: "${CELERY_BROKER_URL:?CELERY_BROKER_URL environment variable is required}"

python manage.py migrate \
    --settings=config.settings.prod

python manage.py migrate account \
    --prune \
    --settings=config.settings.prod

celery -A config worker \
    --loglevel=INFO \
    --pool=solo \
    --without-gossip \
    --without-mingle &
CELERY_WORKER_PID=$!

celery -A config beat \
    --loglevel=INFO \
    --scheduler redbeat.RedBeatScheduler &
CELERY_BEAT_PID=$!

gunicorn config.wsgi:application \
    --workers 1 \
    --threads 6 \
    --bind "0.0.0.0:${PORT:-8000}" \
    --access-logfile - \
    --error-logfile - \
    --capture-output &
GUNICORN_PID=$!

shutdown() {
    kill -TERM \
        "$CELERY_WORKER_PID" \
        "$CELERY_BEAT_PID" \
        "$GUNICORN_PID" \
        2>/dev/null || true

    wait \
        "$CELERY_WORKER_PID" \
        "$CELERY_BEAT_PID" \
        "$GUNICORN_PID" \
        2>/dev/null || true
}

trap shutdown SIGTERM SIGINT

if wait -n \
    "$CELERY_WORKER_PID" \
    "$CELERY_BEAT_PID" \
    "$GUNICORN_PID"
then
    EXIT_CODE=0
else
    EXIT_CODE=$?
fi

shutdown

exit "$EXIT_CODE"