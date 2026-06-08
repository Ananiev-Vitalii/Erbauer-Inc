#!/usr/bin/env bash

set -o errexit

# Optional system dependencies for non-Docker deployments:
# Use this block only on platforms that allow installing system packages
# during the build process. LibreOffice is required for XLSX-to-PDF
# invoice conversion.
#
# apt-get update
# apt-get install -y --no-install-recommends \
#   libreoffice \
#   fonts-dejavu \
#   fonts-liberation

pip install -r requirements.txt

python manage.py collectstatic --no-input --settings=config.settings.prod

python manage.py migrate --settings=config.settings.prod