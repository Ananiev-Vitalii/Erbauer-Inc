# Project Documentation

English is the primary documentation language. A supplementary
[Ukrainian index](../uk/README.md) is available for the developer.

## Project-wide Documentation

- [Backend Testing on Windows](backend_testing.md) — local PostgreSQL and Redis
  setup, isolated Django test settings, PyCharm configuration, test commands,
  and external-service safety boundaries.
- [Database Schema](../db_schema.svg) — the project's database structure.

## Core

- [Shared Rate Limiting Deployment](core/rate_limiting_deployment.md) — client IP
  configuration, Render public/private ingress requirements, shared Redis rate
  limiting, HTTP 503 handling, and deployment verification requirements.

## Main

- [View Algorithms](main/views.md) — request handling, data loading, contact form
  validation and rate limiting, Celery submission, and response outcomes.

## Adding Documentation

Store application documentation at `docs/<language>/<django_application>/<document>.md`.
Keep project-wide documents at the language directory's top level.
Add new documents to the relevant language indexes rather than linking each
document separately from the project's main README.
