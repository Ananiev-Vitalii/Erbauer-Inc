#!/usr/bin/env bash

set -o errexit

apt-get update
apt-get install -y --no-install-recommends \
  libreoffice \
  fonts-dejavu \
  fonts-liberation

pip install -r requirements.txt

python manage.py collectstatic --no-input --settings=config.settings.prod

python manage.py migrate --settings=config.settings.prod