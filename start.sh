#!/bin/sh
set -e

export LIBREOFFICE_PATH="${LIBREOFFICE_PATH:-soffice}"
export LIBREOFFICE_PROFILE_DIR="${LIBREOFFICE_PROFILE_DIR:-/tmp/libreoffice-profile}"

echo "Preparing LibreOffice profile directory..."
mkdir -p "$LIBREOFFICE_PROFILE_DIR"

echo "Starting LibreOffice headless listener..."

$LIBREOFFICE_PATH \
  --headless \
  --nologo \
  --nofirststartwizard \
  --norestore \
  --nodefault \
  "-env:UserInstallation=file://$LIBREOFFICE_PROFILE_DIR" \
  "--accept=socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext" &

echo "LibreOffice listener started"

echo "Running Django migrations..."
python manage.py migrate --settings=config.settings.prod

echo "Starting Gunicorn..."
exec gunicorn config.wsgi:application \
  --workers 1 \
  --threads 6 \
  --bind 0.0.0.0:$PORT