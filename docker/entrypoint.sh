#!/bin/sh
set -e

# Only the `web` service's command starts with `gunicorn` — worker/beat
# (celery ...) and dev's `runserver` never match, so this only ever
# fires where STATIC_ROOT actually needs to exist for nginx to serve.
# --noinput: this runs on every container start/restart, not just once,
# so it must never block on the interactive overwrite-confirmation prompt.
if [ "$1" = "gunicorn" ]; then
    echo "Running collectstatic..."
    python manage.py collectstatic --noinput
fi

exec "$@"
