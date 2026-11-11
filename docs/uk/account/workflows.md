# Робочі процеси Account

`account` відповідає за профілі працівників, календар робочих годин, Simple Invoice
та Cheat Sheet. Authentication, реєстрація й підтвердження email належать `user`;
див. [Алгоритми views User](../user/views.md). Маршрути з `account/urls.py`
підключено під `/profiles/`. Усі account views вимагають login; до POST-запитів
застосовується звичайний Django CSRF-захист.

## Структура та зв'язки

- `models.py`: Position, Employee, Profile, EmployeeWorkHours,
  EmployeeSimpleInvoice, CheatSheet і CheatSheetStep.
- `views.py`, `forms.py`, `validators.py`: координація HTTP, валідація введення
  та відповіді форм. `types.py` описує словники Invoice, адреси й календаря.
- `services/`: календарні операції, створення/обробка Invoice, генерація файлів,
  email та кешування даних Cheat Sheet. `tasks.py` містить worker і retention tasks.
- `storage.py`: приватні PDF Invoice. `signals.py`, зареєстрований через
  `AccountConfig.ready()`, інвалідує кеші даних Cheat Sheet.
- `admin.py` реєструє моделі на custom admin site; `translation.py` перекладає
  імена працівників, назви посад, назви інструкцій та описи кроків.

Employee може існувати без User. Його nullable one-to-one зв'язок `user` поєднує
дані працівника з authentication. Реєстрація в `user` атомарно створює зв'язок
і one-to-one Profile. Profile зберігає аватар. `Employee.is_active` означає чинне
працевлаштування та відрізняється від `User.is_active` й `is_verified`.
Зміна активності Employee автоматично не змінює прапорці User.

Email Employee має case-insensitive унікальність через PostgreSQL constraint
`employee_email_lower_unique` (`Lower("email")`); User має власний constraint.
`Employee.clean()` перевіряє конфлікти з іншими користувачами. `Employee.save()`
зберігає Employee та синхронізує email пов'язаного User в одній транзакції,
зберігаючи регістр адреси. Bulk updates обходять цей метод. Це не workflow
підтвердження нової email-адреси. Перевірки реєстрації та identity описані в User.

Видалення User каскадно видаляє Employee та залежні записи. Видалення через
Employee Admin явно видаляє пов'язаного User або Employee без User. Посаду не можна
видалити, поки на неї є посилання. Більшість profile/invoice views очікують
наявність Employee (і Profile там, де він потрібний); сам login не створює ці
записи для адміністративного акаунта.

## Управління профілем

1. `MyProfileView` завантажує Employee поточного користувача разом із Profile,
   Position, доступними посадами та формами контактів/посади/пароля.
2. `UpdateContactDetailsView` та `UpdateEmployeePositionView` приймають POST лише
   для Employee цього користувача. Форма посади дозволяє вибрати наявну Position;
   додаткової staff permission немає. Успіх повертає нові форми з ознакою успіху,
   помилка зберігає bound-форми. Обидві view повертають HTML partial, зазвичай 200.
3. `UpdatePasswordView` використовує Django `PasswordChangeForm` та
   `update_session_auth_hash()`, зберігаючи чинність поточної сесії. Повертає
   password partial без окремого сервісу зміни пароля.
4. `UpdateAvatarView` приймає POST для Profile поточного користувача. Нові файли
   повинні мати content type JPG, PNG або WEBP та розмір не більше 5 MB;
   ImageField також виконує перевірку зображення. Наявне/порожнє значення не
   потребує нового файла. Нові назви: `profiles/<uuid4 hex><lowercase extension>`.
   Успіх повертає JSON з URL аватара або статичним placeholder; помилка валідації —
   JSON 400. Зображення профілю використовують default storage, а не приватне
   сховище Invoice.

### Валідація контактів

Телефон необов'язковий. Непорожнє значення: десять ASCII-цифр, групи три-три-чотири
з однаковими роздільниками-пробілами, дефісами або крапками, чи `(604) 555-0123`,
за потреби з початковим `+1` або `1` та необов'язковим пробілом після нього.
Валідний номер стає `+1XXXXXXXXXX`. Літери, extensions, Unicode-цифри, змішані
роздільники й інші country codes відхиляються; реальні NANP-коди не перевіряються.

Канадський postal code перевіряється за ASCII case-insensitive шаблоном `A1A 1A1`
з обмеженнями канадських літер та нулем або одним внутрішнім пробілом. Валідне
значення стає uppercase з одним пробілом; некоректне не виправляється до іншого
коду. Контактна форма дозволяє порожній postal code, адресна форма Invoice
вимагає його. Обидві форми прибирають крайні пробіли street/city та роблять першу
літеру city великою. Province вибирається з `CanadianProvince`.

## Календар і робочі години

1. `WorkHoursView` завантажує працевлаштованих Employee з активними, верифікованими
   User. Поточний користувач має входити до цієї множини, інакше 404. GET вибирає
   власний календар, іншого допустимого працівника чи `employee=all`; невідомий
   вибір повертає власний календар. `partial=1` повертає лише вміст календаря.
   Ці працівники можуть переглядати календарі одне одного.
2. `month=YYYY-MM` вибирає один із дванадцяти календарних місяців: поточний та
   одинадцять попередніх. Некоректний/недоступний вибір повертає поточний місяць.
   Календарі пакетно завантажують записи годин і блокувальні Invoice.
3. `WorkHoursUpdateView` приймає лише AJAX POST, інакше 404. Завжди вибирає
   `request.user.employee`, а не переданий клієнтом Employee ID. На відміну від
   списку календарів, endpoint не повторює фільтри працевлаштування/verification.
4. `save_employee_work_hours()` перевіряє дату й значення, блокує Employee в
   `atomic()`, перевіряє блокування Invoice, потім блокує наявний запис дня.
   Майбутні дати та дати до дванадцятимісячного cutoff заборонено. Значення має
   бути скінченним, не більше 24 годин, максимум із двома десятковими знаками та
   кроком 0.10 години; десяткова кома дозволена. Порожнє значення чи нуль видаляє
   незаблокований запис.
5. Збереження викликає `full_clean()`; PostgreSQL гарантує один запис Employee/date
   та `0 < hours <= 24`. Помилки валідації повертають JSON 400. Успіх повертає
   JSON зі збереженим/видаленим значенням і перерахованою сумою місяця.

### Години Invoice та календаря

Години Invoice можна ввести вручну без записів календаря, і вони можуть
відрізнятися від їхньої суми. Валідація Invoice вимагає додатні години, а не
рівність календарній сумі чи календарний крок 0.10. Будь-який Invoice, що
перетинається з періодом і має непрострочений статус `PROCESSING`/`PREPARING` або
`SENT`, блокує весь період включно з межами та днями без записів. Прив'язаний
запис також не можна редагувати.

Для кожного блокувального періоду відображена місячна сума замінює календарну
суму годинами Invoice. Якщо суми різні, денні години цього періоду приховуються
в календарі; збережені записи не переписуються. Read-only запити календаря
ігнорують прострочені активні Invoice, не змінюючи їхнього статусу.

## Створення Simple Invoice

`SimpleInvoiceCreateView` повертає повну форму на GET та HTML partial на POST.
GET отримує номер/rate/GST account/GST/WSBC останнього Invoice через ORM subqueries
і пропонує період від початку поточного місяця до сьогодні. Наступний номер
пропонується лише поки останній менший за 99; номер не є унікальним ідентифікатором
БД. Адреса Invoice є snapshot цього запиту та не оновлює контакти Employee.

1. Перевірити `EmployeeInvoiceForm` і `SimpleInvoiceForm`. Номер — 1–99, години —
   додатні, rate — невід'ємний, GST/WSBC — 0–100% (defaults 5 і 0). Непорожній
   GST account нормалізується до `123456789 RT0001`. Період включно з межами має
   бути в одному доступному календарному місяці, завершуватися не пізніше
   сьогодні та не перетинатися з блокувальним Invoice цього Employee.
2. Викликати `submit_simple_invoice()`. Повторно перевірити правила періоду,
   увійти в `atomic()`, заблокувати Employee, повторити перевірку перетину,
   викликати `full_clean()` та зберегти Invoice у `PROCESSING`.
3. Зареєструвати `process_simple_invoice_task.apply_async()` через
   `transaction.on_commit()`, передавши Invoice ID, адресу та broker expiry
   300 секунд. Rollback скасовує публікацію. PDF/email не обробляються всередині
   транзакції створення.
4. За очікуваної Kombu/Redis помилки публікації записати лог і спробувати перевести
   лише досі `PROCESSING` Invoice у `FAILED`. Уже захоплена worker задача не
   скасовується. Підтверджений збій чи невідомий стан БД стає
   `SimpleInvoicePublicationError` у bound-формі; committed-записи залишаються.
5. Успіх повертає нові форми та `invoice_id` для polling статусу. Валідація й
   контрольовані помилки публікації повертають bound partial, зазвичай HTTP 200.
   POST-рендеринг додає CSRF та обходить глобальні context processors. Зовнішня
   транзакція відклала б публікацію/повідомлення про її помилку до свого commit;
   поточна view не обгортає service в зовнішню транзакцію.

`SimpleInvoicePeriodPreviewView` — AJAX GET endpoint: перевіряє вибрані
year/month/day, повідомляє про перетин і доступні календарні години та повертає
`can_submit`. Некоректний рік дає 400; недоступний місяць замінюється останнім
доступним, а значення днів отримують defaults/обмежуються його діапазоном.
Зворотний/конфліктний період описується в preview payload. Він не створює Invoice,
не резервує години й не переводить прострочені записи; submission повторює всі
перевірки під lock.

## Worker, статуси та транзакції

| Статус | Значення та блокування періоду |
| --- | --- |
| `PROCESSING` | Збережено/поставлено в чергу; період логічно заблоковано до п'яти хвилин. |
| `PREPARING` | Worker захопив Invoice та прив'язав наявні години; deadline той самий. |
| `SENT` | Email-виклик успішно завершився, finalization committed; період залишається заблокованим. |
| `FAILED` | Обробка завершилася помилкою/timeout; резервування знято, перетин більше не блокує. |

1. `process_simple_invoice_task` перевіряє наявність, статус і timeout. Дубльована
   задача не може захопити Invoice, який уже не в `PROCESSING`.
2. `reserve_work_hours_for_invoice()` блокує Employee, потім Invoice в `atomic()`.
   Повторно перевіряє статус/deadline/перетин, встановлює `PREPARING` та прив'язує
   незарезервовані записи календаря в періоді. Claim і резервування commit разом.
3. `process_simple_invoice()` створює тимчасові XLSX/PDF та завантажує PDF поза
   DB locks. Коротка транзакція повторно перевіряє `PREPARING` claim/deadline,
   звільняє locks, потім надсилається email.
4. `mark_simple_invoice_sent()` знову блокує Employee, потім Invoice, повторює
   перевірку claim/deadline та атомарно записує PDF reference і `SENT`.
   Наявні резервування годин залишаються прив'язаними.
5. Cancellation/expiry зупиняє задачу. Інші винятки запускають guarded failure
   transition для очікуваного статусу, потім передаються Celery. Failure handling
   блокує Employee перед Invoice, знімає прив'язки годин і очищає PDF reference;
   прострочені пов'язані файли видаляються після commit. Результати задачі
   ігноруються; автоматичного task retry немає.

П'ятихвилинний deadline рахується від `created_at`, а не старту worker чи
`PREPARING`. Після досягнення межі активні Invoice можуть ліниво стати `FAILED`
під час submission, відповідних змін годин, history/status/download перевірок
або worker guards. Окремої періодичної п'ятихвилинної cleanup-задачі немає.
Захист від перетину реалізують services через Employee locks, а не PostgreSQL
exclusion constraint; записи в обхід services не отримують цієї гарантії.

PostgreSQL, Redis, Cloudinary та email не утворюють єдину атомарну транзакцію.
Зокрема, provider може прийняти лист до timeout чи до збою фінального DB commit.
Timeout під час надсилання може залишити `FAILED` після прийняття листа;
повторний submission може надіслати дублікат. `SENT` не підтверджує доставлення
до inbox. Exactly-once гарантії або provider reconciliation немає. Очищення
uploaded-файла зберігає persisted PDF reference та пропускає видалення, якщо стан
БД не можна встановити; можливі orphan-файли є прийнятим компромісом.

## XLSX, PDF, email та інфраструктура

- `simple_invoice_xlsx.py` заповнює `invoice_templates/simple-invoice.xlsx` через
  openpyxl. C6–C10 після присвоєння примусово мають string type; недовірений текст
  не стає формулою. E14/F14 залишаються числовими. Формули рядків/subtotal/total
  шаблону збережені; Python задає GST `G27=G26*<gst>%` і WSBC `G28=G26*<wsbc>%`.
  LibreOffice обчислює spreadsheet formulas під час перетворення на PDF.
- `simple_invoice_pdf.py` запускає headless LibreOffice з окремим тимчасовим
  user profile і subprocess timeout 180 секунд. `LIBREOFFICE_PATH` вибирає
  executable, fallback — `soffice`. Повідомлення conversion errors не містять
  сирого process output або приватних шляхів команди.
- `PrivateInvoiceCloudinaryStorage` явно зберігає PDF Invoice як private raw
  resources. Авторизоване завантаження використовує signed attachment URLs на
  300 секунд; власник такого посилання має тимчасовий доступ. Аватари й
  зображення Cheat Sheet використовують налаштований default media storage.
- `simple_invoice_email.py` надсилає локальний PDF attachment на
  `SIMPLE_INVOICE_RECIPIENT_EMAIL` та email Employee через `core.services.email`
  і налаштований Anymail/Brevo backend. Branding бере єдиний активний
  CompanyProfile, а за його відсутності — display name/address із
  `DEFAULT_FROM_EMAIL`. Invoice task не передає мову request і не використовує
  `translation.override()`; email рендериться активною/default мовою worker.
- Redis забезпечує налаштований Django data cache, Celery broker та RedBeat
  scheduler. Це різні відповідальності/namespaces; статуси Invoice й резервування
  зберігаються в PostgreSQL. Account views не додають власного Redis rate limiter.
  Конфігурація cache може використовувати fallback LocMemCache.

## Історія, завантаження та retention

`SimpleInvoiceHistoryView` показує лише Invoice поточного користувача, створені
в rolling 36-month retention window, від нових до старих. Прострочені активні
Invoice переводяться у failure; потім retained list фільтрується за invoice year
або періодом створення (3/6/12/24/36 місяців). Доступні роки беруться з цього
списку; pagination немає. `PREPARING` використовує processing-оформлення, але
власну локалізовану назву статусу.

`SimpleInvoiceStatusView` приймає лише AJAX GET. Status і
`SimpleInvoiceDownloadView` шукають Invoice власника та перевіряють timeout.
Відсутній або чужий ID дає 404. Download повертає 409, якщо немає `SENT` із PDF;
інакше redirect на signed Cloudinary URL. Work-hour update, period preview,
status і download endpoints використовують `never_cache`.

Celery Beat запускає `cleanup_expired_simple_invoices` у неділю о 03:00 та
`cleanup_expired_work_hours` о 04:15 у налаштованій Celery timezone
(`America/Vancouver`). Invoice cleanup видаляє записи, старші за rolling
36-month cutoff. Work-hour cleanup видаляє дати до першого retained місяця
дванадцятимісячного вікна, включно з прив'язаними записами; сам Invoice не видаляє.
Cleanup використовує транзакції для кожного Employee та Employee-before-Invoice
locks. `django-cleanup` обробляє видалення файлів під час видалення моделей.
Щотижневе фізичне очищення й history window відрізняються; потрібні чинні Beat/workers.

## Cheat Sheet та інвалідація кешу

`CheatSheetView` повертає кешований список інструкцій на повний GET або кешовані
кроки для `cheat_sheet_id` при `partial=1`. Некоректний/відсутній ID дає порожній
список кроків; окремої detail-object 404 перевірки немає. Admin редагує перекладені
інструкції/кроки й пропонує наступний номер кроку. PostgreSQL гарантує унікальні
номери кроків у межах інструкції.

Кешуються лише обчислені списки даних, а не HTML чи unevaluated QuerySets:

- `account:cheat_sheets:list:<language>`, сортування за name;
- `account:cheat_sheet:steps:<id>:<language>`, сортування за step number.

Обидва використовують `CACHE_DEFAULT_TIMEOUT` (default 900 секунд), активну Django
мову та налаштований backend key prefix. Save/delete signals після commit
планують адресний `delete_many()` для всіх `settings.LANGUAGES`. Зміна інструкції
очищає список та її кроки; зміна кроку — відповідні кроки; перенесення кроку —
старого й нового батьків. Rollback зберігає кеш. `QuerySet.update()` і bulk writes
обходять save signals. Конкурентне заповнення може повернути застарілі дані після
інвалідації; TTL обмежує їхній строк життя. Redis-помилки інвалідації логуються
та можуть залишити старий вміст до expiry; для cache read failures тут немає
окремого fallback/503 handler.

## Services та діагностика

| Модуль у `account/services/` | Відповідальність |
| --- | --- |
| `work_hours.py` | Вибір місяця, валідація/запис годин, календарі та effective totals. |
| `simple_invoice_period.py` | Доступність періоду, перевірка перетину, суми й резервування годин. |
| `simple_invoice_submission.py` | Транзакційне створення та публікація задачі після commit. |
| `simple_invoice_processing.py` | Locks, guarded state transitions, expiry і зняття резервування. |
| `simple_invoice_service.py` | Координація файлів/email та очищення uploaded-файлів. |
| `simple_invoice_xlsx.py`, `simple_invoice_pdf.py` | Заповнення шаблону й конвертація LibreOffice. |
| `simple_invoice_email.py` | Адресати, branding, attachment і shared email sender. |
| `cache.py` | Мовний кеш даних Cheat Sheet та адресна інвалідація. |

Помилки account використовують налаштований stderr handler (`propagate=False`)
та `EmailErrorFormatter`: залишаються тип винятку/місця traceback, а повідомлення
provider, деталі chained exceptions і locals прибираються. Власні повідомлення
логів використовують Invoice ID і типи винятків замість адрес, токенів та вмісту
файлів. `AccountTaskFailureFilter` приховує аргументи/exception data помилок account
tasks у `celery.app.trace`; `AccountCleanupFailureFilter` очищає повідомлення
account file failures із `django_cleanup.handlers`. Celery повідомляє про
передані task exceptions; другий загальний task-error log не додається. Логи
доступні в Logs відповідного Render web/worker service з урахуванням logging level.

## Backend-перевірки

Налаштування PostgreSQL Docker і runner safety описані в
[Ізольованому backend-тестуванні](../backend_testing.md). В активованому середовищі:

```powershell
python manage.py test account.tests --settings=config.settings.test
python -m flake8 account
```

У головному Erbauer успішно пройшли 34 backend-тести account на PostgreSQL і Flake8.
Набір перевіряє invoice lifecycle/concurrency/publication, доступ до робочих годин
і правила періодів, валідацію профілю, XLSX formula protection, інвалідацію кешу
при commit/rollback та log redaction. Зовнішні email, Cloudinary, Celery publication
та LibreOffice підмінені mocks. Цим тестам не потрібні real Redis opt-in, worker
або production credentials; вони не підтверджують реальне доставлення листів,
Cloudinary permissions чи LibreOffice rendering у deployment.
