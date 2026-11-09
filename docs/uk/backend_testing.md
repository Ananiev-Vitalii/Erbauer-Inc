# Ізольоване backend-тестування

Використовуємо стандартний Django testing framework: `unittest`,
`SimpleTestCase`, `TestCase`, `TransactionTestCase` і `unittest.mock`.
Ця конфігурація не додає самих тестів і не перевіряє frontend.

## 1. Передумови Windows

1. Запустіть Docker Desktop із Linux containers і локальним Docker context.
   Перевірте його через `docker context show`: не використовуйте remote host.
2. Відкрийте PowerShell у корені Erbauer та активуйте проєктну `.venv`:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

3. Використовуйте залежності з `requirements.txt`. Окремі pytest, worker,
   Beat, Cloudinary credentials, Brevo credentials і LibreOffice не потрібні.
4. Не створюйте `.env.test` і не підключайте звичайний `.env` до test configuration.
   Вільними мають бути порти `55432` і `56379`.

## 2. Запуск PostgreSQL

Забороніть Compose автоматично читати кореневий `.env`, потім запустіть
тільки тестовий PostgreSQL:

```powershell
$env:COMPOSE_DISABLE_ENV_FILE = "1"
docker compose -f compose.test.yaml up -d --wait postgres
```

PostgreSQL доступний тільки через `127.0.0.1:55432`. Контейнер має окремі
несекретні test-only credentials: роль `erbauer_test`, пароль
`erbauer_test_only`, службова база `erbauer_test_control`.
Ці значення не можна використовувати в dev або production.

Django створює окрему БД `test_erbauer_backend`, застосовує migrations і
видаляє її після звичайного завершення. `migrate` вручну не потрібний.
Службова БД не містить таблиць розробки. PostgreSQL data directory знаходиться
у tmpfs: його вміст не призначений для тривалого зберігання.

Не запускайте одночасно кілька test suites на цій конфігурації: ім'я БД спільне.
Не використовуйте production-тунелі на тестових портах. Початковий runner
підтримує тільки послідовний запуск без `--parallel`.

## 3. Перевірка налаштувань і запуск

Команди нижче запускаються вручну після підготовки Docker:

```powershell
python manage.py check --settings=config.settings.test
python manage.py check --settings=config.settings.test --database default
python manage.py test main.tests core.tests --settings=config.settings.test --exclude-tag=redis
```

Основна команда завжди явно обирає test settings. Звичайний `.env` не
завантажується ані через `manage.py`, ані через `base.py`.
Відомі application credentials у середовищі тестового Python-процесу
замінюються несекретними значеннями до імпорту base settings і provider SDKs.
Змінні libpq `PG*` також спрямовані на тестовий контейнер; успадковані
service/password files не використовуються.
Файли environment при цьому не редагуються.

Альтернативно для поточного PowerShell-процесу:

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings.test"
python manage.py test main.tests core.tests --exclude-tag=redis
Remove-Item Env:DJANGO_SETTINGS_MODULE
```

`test` без явного вибору test settings завершується помилкою до завантаження
звичайного `.env`. Після тестування не залишайте test settings у конфігурації
запуску dev-сервера. Не використовуйте `--keepdb` на початковому етапі.

Поки тестових модулів немає, Django може повідомити `0 tests` і пропустити
створення БД. Такий результат не підтверджує роботу migrations або створення
тестової БД. Це перевіримо з першими database tests.

## 4. PyCharm

Створіть окрему **Python Run Configuration**:

- Script: `manage.py` у корені проєкту.
- Parameters: `test main.tests core.tests --settings=config.settings.test --exclude-tag=redis`.
- Interpreter: проєктна `.venv`.
- Working directory: корінь проєкту.
- Environment: `DJANGO_SETTINGS_MODULE=config.settings.test`.
- Вимкніть автоматичне підключення `.env`/EnvFile для цієї конфігурації.

Спочатку запустіть PostgreSQL через Compose. Використовуйте цю конфігурацію,
а не загальний Python unittest runner: захисний support підключений через
Django `TEST_RUNNER`. IDE test configurations, які обходять Django runner,
не забезпечують описаних нижче runtime guards.

## 5. Межі ізоляції

- Звичайний cache — окремий `LocMemCache`. Sessions зберігають `cached_db`
  і використовують тестову БД та цей локальний cache.
- Email — memory backend, адреси закінчуються на `.invalid`.
- Celery — `memory://`, без result backend, eager mode і Beat schedule.
  Непідмінені `Task.apply_async()` та `Celery.send_task()` заблоковані runner.
  У майбутніх tests використовуйте mocks у місці виклику. Task wrapper
  перевіряйте прямим викликом із підміненим сервісом.
- Default storage — `FileSystemStorage`. Runner створює унікальний
  `TemporaryDirectory` і прибирає його навіть при винятку. Запуск `check`
  не створює цей каталог; поза runner fallback media path лежить у системному tmp.
- `PrivateInvoiceCloudinaryStorage` заданий прямо у полі моделі. Runner
  блокує його `open`, `save`, `delete`, `exists`, `url`, `size`.
  Для invoice tests потрібен адресний mock або локальна підміна storage.
  Cloudinary/storage-моделі production не змінюються.
- Непідмінені HTTP-виклики Requests/urllib3 та запуск зовнішніх процесів
  блокуються. Turnstile, Brevo, Cloudinary і LibreOffice не викликаються.
- Python socket connections заборонені, крім opt-in Redis endpoint.
  PostgreSQL використовує native libpq, тому його адреса, роль і допустимі
  назви БД додатково перевіряються перед створенням Django connection.
- Guards охоплюють discovery, database setup, tests і teardown стандартного
  runner. До його старту діють ізольовані settings і несекретні credentials.

Це захист від випадкових зовнішніх операцій, а не sandbox для недовіреного
Python-коду. Прямий виклик стороннього native driver або навмисна заміна
guards тестом може обійти його. Не запускайте test suite з production credentials
чи tunnel endpoints. Збої `django-cleanup` можуть бути перехоплені бібліотекою
та залоговані; заблокований виклик не означає успішне видалення файла.

Не запускайте worker, Beat, `start.sh` або production Dockerfile для тестів.
Нові зовнішні інтеграції потребуватимуть перегляду test boundaries.

## 6. Майбутні Redis integration tests

Redis не потрібен звичайному набору. Для майбутніх Lua tests:

```powershell
$env:COMPOSE_DISABLE_ENV_FILE = "1"
docker compose -f compose.test.yaml --profile redis up -d --wait
$env:TEST_REDIS_INTEGRATION = "1"
python manage.py test core.tests.test_rate_limit_integration --settings=config.settings.test --tag=redis
Remove-Item Env:TEST_REDIS_INTEGRATION
```

Opt-in дозволяє socket connections лише на `127.0.0.1:56379`; він не
перемикає default cache автоматично. Redis запускається без persistence.
Налаштування `settings.TEST_REDIS_CACHE` містить Django `RedisCache` для
цього endpoint і випадковий тестовий `KEY_PREFIX`.

Майбутні integration tests мають:

1. Отримати tag `redis` і пропускатися, якщо `TEST_REDIS_INTEGRATION` вимкнений.
2. Через `override_settings` тимчасово встановити `TEST_REDIS_CACHE` як
   `CACHES['default']`: Lua adapter використовує саме default alias.
3. Використовувати окремі scopes/ключі для кожного тесту.
4. Видаляти тільки власні відомі ключі через адресні операції.
5. Не використовувати `FLUSHALL`, `FLUSHDB` або глобальний `cache.clear()`.
6. При ввімкненому opt-in вважати недоступний Redis помилкою, а не skip.

Без opt-in Redis-звернення блокуються. TTL, concurrency і Lua перевірятимемо
лише після появи integration tests, а не за допомогою LocMemCache.

## 7. Завершення

```powershell
docker compose -f compose.test.yaml --profile redis down
```

Налаштування не використовують dev/prod volumes. Для запуску достатньо
Docker Desktop, `.venv`, проєктних залежностей і явно обраних test settings.
