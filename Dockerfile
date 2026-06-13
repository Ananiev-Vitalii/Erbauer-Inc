FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=config.settings.prod

ENV LIBREOFFICE_PATH=soffice
ENV LIBREOFFICE_PROFILE_DIR=/tmp/libreoffice-profile
ENV LIBREOFFICE_HOST=127.0.0.1
ENV LIBREOFFICE_PORT=2002

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice \
        fonts-dejavu \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN python manage.py collectstatic --no-input --settings=config.settings.prod

RUN sed -i 's/\r$//' /app/start.sh \
    && chmod +x /app/start.sh

CMD ["/app/start.sh"]