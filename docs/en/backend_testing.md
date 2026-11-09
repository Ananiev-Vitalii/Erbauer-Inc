# Isolated Backend Testing

We use Django's standard testing framework: `unittest`,
`SimpleTestCase`, `TestCase`, `TransactionTestCase`, and `unittest.mock`.
This configuration does not add tests or test the frontend.

## 1. Windows Prerequisites

1. Start Docker Desktop with Linux containers and a local Docker context.
   Check it with `docker context show`: do not use a remote host.
2. Open PowerShell in the Erbauer project root and activate the project `.venv`:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. Use the dependencies from `requirements.txt`. No separate pytest installation,
   worker, Beat, Cloudinary credentials, Brevo credentials, or LibreOffice is needed.
4. Do not create `.env.test` or attach the regular `.env` to the test configuration.
   Ports `55432` and `56379` must be available.

## 2. Starting PostgreSQL

Prevent Compose from automatically reading the root `.env`, then start
only the test PostgreSQL service:

```powershell
$env:COMPOSE_DISABLE_ENV_FILE = "1"
docker compose -f compose.test.yaml up -d --wait postgres
```

PostgreSQL is exposed only through `127.0.0.1:55432`. The container uses separate,
non-secret test-only credentials: role `erbauer_test`, password
`erbauer_test_only`, and control database `erbauer_test_control`.
Do not use these values in development or production.

Django creates a separate database, `test_erbauer_backend`, applies migrations,
and drops it after normal completion. Running `migrate` manually is not required.
The control database does not contain development tables. The PostgreSQL data
directory uses tmpfs: its contents are not intended for long-term storage.

Do not run multiple test suites concurrently with this configuration: they share
the database name. Do not use production tunnels on the test ports. The initial
runner supports only serial execution, without `--parallel`.

## 3. Checking Settings and Running Tests

Run the following commands manually after preparing Docker:

```powershell
python manage.py check --settings=config.settings.test
python manage.py check --settings=config.settings.test --database default
python manage.py test --settings=config.settings.test
```

The main command always selects test settings explicitly. Neither `manage.py`
nor `base.py` loads the regular `.env`.
Known application credentials in the test Python process environment are replaced
with non-secret values before importing base settings and provider SDKs.
The libpq `PG*` variables also point to the test container; inherited
service/password files are not used.
Environment files are not modified.

Alternatively, for the current PowerShell process:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.test"
python manage.py test
Remove-Item Env:DJANGO_SETTINGS_MODULE
```

Running `test` without explicitly selecting test settings fails before loading
the regular `.env`. After testing, do not leave test settings selected in the
development server configuration. Do not use `--keepdb` during the initial stage.

While there are no test modules, Django may report `0 tests` and skip database
creation. This result does not verify migrations or test database creation.
We will verify them with the first database tests.

## 4. PyCharm

Create a separate **Python Run Configuration**:

- Script: `manage.py` in the project root.
- Parameters: `test --settings=config.settings.test`.
- Interpreter: the project `.venv`.
- Working directory: the project root.
- Environment: `DJANGO_SETTINGS_MODULE=config.settings.test`.
- Disable automatic `.env`/EnvFile loading for this configuration.

Start PostgreSQL through Compose first. Use this configuration rather than the
generic Python unittest runner: the safety support is connected through Django's
`TEST_RUNNER`. IDE test configurations that bypass the Django runner do not
provide the runtime guards described below.

## 5. Isolation Boundaries

- The regular cache is a separate `LocMemCache`. Sessions retain `cached_db`
  and use the test database and this local cache.
- Email uses the memory backend, with addresses ending in `.invalid`.
- Celery uses `memory://`, with no result backend, eager mode disabled, and no
  Beat schedule. The runner blocks unmocked `Task.apply_async()` and
  `Celery.send_task()` calls. Future tests should mock the boundary where it is
  called. Test task wrappers by calling them directly with the service mocked.
- Default storage is `FileSystemStorage`. The runner creates a unique
  `TemporaryDirectory` and removes it even if an exception occurs. Running `check`
  does not create this directory; outside the runner, the fallback media path
  is in the system temporary directory.
- `PrivateInvoiceCloudinaryStorage` is specified directly on the model field.
  The runner blocks its `open`, `save`, `delete`, `exists`, `url`, and `size`
  operations. Invoice tests need a targeted mock or a local storage replacement.
  Production Cloudinary/storage models are not changed.
- Unmocked Requests/urllib3 HTTP calls and external process execution are blocked.
  Turnstile, Brevo, Cloudinary, and LibreOffice are not called.
- Python socket connections are blocked except for the opt-in Redis endpoint.
  PostgreSQL uses native libpq, so its address, role, and allowed database names
  are additionally checked before creating a Django connection.
- The guards cover discovery, database setup, tests, and teardown in the standard
  runner. Isolated settings and non-secret credentials apply before it starts.

This protects against accidental external operations; it is not a sandbox for
untrusted Python code. Direct calls to a third-party native driver or deliberate
replacement of guards by a test can bypass this protection. Do not run the test
suite with production credentials or tunnel endpoints. The `django-cleanup`
library may catch and log failures; a blocked call does not mean that a file
was deleted successfully.

Do not start a worker, Beat, `start.sh`, or the production Dockerfile for tests.
New external integrations will require a review of the test boundaries.

## 6. Future Redis Integration Tests

The regular suite does not need Redis. For future Lua tests:

```powershell
$env:COMPOSE_DISABLE_ENV_FILE = "1"
docker compose -f compose.test.yaml --profile redis up -d --wait
$env:TEST_REDIS_INTEGRATION = "1"
python manage.py test --settings=config.settings.test --tag=redis
Remove-Item Env:TEST_REDIS_INTEGRATION
```

Opt-in permits socket connections only to `127.0.0.1:56379`; it does not
automatically switch the default cache. Redis runs without persistence.
The `settings.TEST_REDIS_CACHE` setting provides a Django `RedisCache`
configuration for this endpoint and a random test `KEY_PREFIX`.

Future integration tests must:

1. Use the `redis` tag and skip when `TEST_REDIS_INTEGRATION` is disabled.
2. Use `override_settings` to temporarily set `TEST_REDIS_CACHE` as
   `CACHES['default']`: the Lua adapter uses this specific default alias.
3. Use separate scopes/keys for each test.
4. Delete only their own known keys through targeted operations.
5. Never use `FLUSHALL`, `FLUSHDB`, or a global `cache.clear()`.
6. Treat unavailable Redis as an error, not a skip, when opt-in is enabled.

Without opt-in, Redis calls are blocked. We will verify TTL, concurrency, and
Lua only after adding integration tests, not through LocMemCache.

## 7. Shutting Down

```powershell
docker compose -f compose.test.yaml --profile redis down
```

The configuration does not use development/production volumes. Running it
requires only Docker Desktop, `.venv`, the project dependencies, and explicitly
selected test settings.
