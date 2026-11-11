# Account Workflows

`account` owns employee profiles, work-hour calendars, Simple Invoices and Cheat
Sheets. Authentication, registration and email verification belong to `user`;
see [User View Algorithms](../user/views.md). Routes in `account/urls.py` are
mounted under `/profiles/`. All account views require login; normal Django CSRF
protection applies to POST requests.

## Structure and Relationships

- `models.py`: Position, Employee, Profile, EmployeeWorkHours,
  EmployeeSimpleInvoice, CheatSheet and CheatSheetStep.
- `views.py`, `forms.py`, `validators.py`: HTTP coordination, input validation
  and form responses. `types.py` describes invoice/address/calendar dictionaries.
- `services/`: calendar operations, invoice submission/processing, file generation,
  email and Cheat Sheet data caching. `tasks.py` contains worker and retention tasks.
- `storage.py`: private invoice PDFs. `signals.py`, registered in
  `AccountConfig.ready()`, invalidates Cheat Sheet data caches.
- `admin.py` registers models on the custom admin site; `translation.py`
  translates employee names, position names, guide names and step descriptions.

Employee may exist without User. Its nullable one-to-one `user` link connects
employment data to authentication. Registration in `user` creates the link and
the one-to-one Profile atomically. Profile stores the avatar. `Employee.is_active`
means currently employed; it is distinct from `User.is_active` and `is_verified`.
Changing Employee activity does not automatically change the User flags.

Employee email is unique case-insensitively through PostgreSQL
`employee_email_lower_unique` (`Lower("email")`); User has its own constraint.
`Employee.clean()` checks conflicts with other users. `Employee.save()` saves
Employee and synchronizes linked User email in one transaction, preserving the
email spelling. Bulk updates bypass this method. This is not a new-email
verification workflow. See the User guide for registration and identity checks.

Deleting User cascades to Employee and its dependent records. Employee Admin
deletion explicitly deletes the linked User, or the unlinked Employee. Position
is protected while referenced. Most profile/invoice views expect an existing
Employee (and Profile where needed); login alone does not create these records
for an administrative account.

## Profile Management

1. `MyProfileView` loads the current user's Employee with Profile and Position,
   available positions and contact/position/password forms.
2. `UpdateContactDetailsView` and `UpdateEmployeePositionView` accept POSTs for
   that user's Employee only. The position form allows selecting an existing
   Position; no additional staff permission is checked. Successful saves return
   fresh forms marked successful; invalid submissions retain their bound forms.
   Both return HTML partials, normally with HTTP 200.
3. `UpdatePasswordView` uses Django `PasswordChangeForm` and
   `update_session_auth_hash()` to keep the current session valid. It returns
   the password partial without adding a separate password service.
4. `UpdateAvatarView` accepts POSTs for the current user's Profile. New uploads
   must be JPG, PNG or WEBP by uploaded content type and at most 5 MB; the
   ImageField also performs image validation. Existing/empty values need no new
   upload. New names use `profiles/<uuid4 hex><lowercase extension>`.
   Success returns JSON with the avatar URL or static placeholder; validation
   failure returns JSON with HTTP 400. Other profile images use default storage,
   not the private invoice storage.

### Contact Validation

Phone is optional. Accepted nonempty values are ten ASCII digits, matching
three-three-four groups separated by spaces, hyphens or dots, or `(604) 555-0123`,
optionally prefixed by `+1` or `1` with an optional following space. Valid values
become `+1XXXXXXXXXX`. Letters, extensions, Unicode digits, mixed separators and
other country codes are rejected; actual NANP allocation is not checked.

Canadian postal codes use the ASCII, case-insensitive `A1A 1A1` pattern with
Canadian letter restrictions and zero or one internal space. Valid input becomes
uppercase with one space; invalid input is not repaired into a different code.
Contact details allow an empty postal code; the invoice address form requires
it. Both forms trim street/city values and capitalize the city's first character.
Province is selected from `CanadianProvince`.

## Calendar and Work Hours

1. `WorkHoursView` loads employees who are employed and have active, verified
   Users. The requester must be in that set or receives 404. GET selects the
   current employee, another eligible employee or `employee=all`; unsupported
   selection falls back to the requester's calendar. `partial=1` returns only
   the calendar content. These employees may view one another's calendars.
2. `month=YYYY-MM` selects one of twelve calendar months: the current month and
   eleven previous months. Invalid/unavailable selection falls back to this month.
   Calendars load work-hour rows and blocking invoices in batches.
3. `WorkHoursUpdateView` accepts AJAX POST only, otherwise 404. It always selects
   `request.user.employee`, not an employee ID supplied by the client. Unlike the
   calendar list, this endpoint does not repeat the employed/verified filters.
4. `save_employee_work_hours()` validates the date and value, locks Employee in
   `atomic()`, checks invoice locks, then locks the existing day's row. Future
   dates and dates before the twelve-month cutoff are rejected. Values must be
   finite, at most 24 hours, with at most two decimal places and 0.10-hour steps;
   comma decimals are accepted. Empty input or zero deletes an unlocked entry.
5. Save uses `full_clean()`; PostgreSQL guarantees one row per Employee/date and
   `0 < hours <= 24`. Validation errors return JSON 400. Success returns JSON
   with the saved/deleted value and recalculated month total.

### Invoice Hours Versus Calendar Hours

Invoice hours may be entered manually, with no calendar rows, and may differ
from their sum. Invoice validation requires positive hours, not equality with
calendar hours or the calendar's 0.10-hour step. Any overlapping, unexpired
`PROCESSING`/`PREPARING` or `SENT` invoice blocks the entire inclusive date period,
including days with no stored hours. A linked row also cannot be edited.

For each blocking period, the displayed calendar month total replaces the raw
calendar sum with the Invoice's hours. If the two sums differ, daily hours in
that period are hidden in the calendar; stored rows are not rewritten. Read-only
calendar requests ignore expired active invoices without changing their status.

## Simple Invoice Submission

`SimpleInvoiceCreateView` serves the full form on GET and an HTML partial on POST.
GET preloads the latest invoice's number/rate/GST account/GST/WSBC using ORM
subqueries and defaults the period to this month through today. The next number
is suggested only while the last number is below 99; numbering is not a unique
database identifier. The invoice address is a submission snapshot and does not
update Employee contact details.

1. Validate `EmployeeInvoiceForm` and `SimpleInvoiceForm`. Invoice numbers are
   1–99, hours are positive, rate is nonnegative, GST/WSBC percentages are 0–100
   (defaults 5 and 0). A nonempty GST account is normalized to `123456789 RT0001`.
   The inclusive period must fit one available calendar month, end no later than
   today, and not overlap a blocking Invoice for the same Employee.
2. Call `submit_simple_invoice()`. Recheck period rules, enter `atomic()`, lock
   Employee, recheck overlap, run `full_clean()` and save a `PROCESSING` invoice.
3. Register `process_simple_invoice_task.apply_async()` through
   `transaction.on_commit()`, passing Invoice ID and address data with a
   300-second broker expiry. Rollback discards publication. No PDF/email work
   occurs inside the submission transaction.
4. On expected Kombu/Redis publication failure, log the error and attempt to mark
   only a still-`PROCESSING` invoice `FAILED`. A task already claimed by a worker
   is not cancelled. A confirmed failure or unknown database state becomes
   `SimpleInvoicePublicationError`, shown on the bound form; committed records stay.
5. Success returns fresh forms and `invoice_id` for status polling. Validation
   and controlled publication errors return the bound partial, normally HTTP 200.
   POST rendering injects CSRF and bypasses global context processors. An outer
   transaction would defer publication/error reporting until its own commit;
   the current view does not wrap the service in an outer transaction.

`SimpleInvoicePeriodPreviewView` is an AJAX GET endpoint: it checks available
year/month/day selections, reports overlap and available calendar hours, and
returns `can_submit`. Invalid years return 400; an unavailable month falls back
to the latest available month, and day values are defaulted/clamped to its range.
Reversed/conflicting periods are reported in the preview payload. It does not
create an Invoice, reserve hours or expire rows; submission revalidates
everything under lock.

## Worker, States and Transactions

| State | Meaning and period locking |
| --- | --- |
| `PROCESSING` | Saved/queued; the period is logically blocked for up to five minutes. |
| `PREPARING` | A worker claimed the invoice and linked existing hours; same deadline. |
| `SENT` | Email call returned successfully and finalization committed; period stays locked. |
| `FAILED` | Processing failed/expired; reservations are released and overlap no longer blocks. |

1. `process_simple_invoice_task` checks existence, status and expiry. Duplicate
   tasks cannot claim an invoice already outside `PROCESSING`.
2. `reserve_work_hours_for_invoice()` locks Employee, then Invoice in `atomic()`.
   Recheck status/deadline/overlap, set `PREPARING`, and link unreserved calendar
   rows in the period. Commit the claim and reservations together.
3. `process_simple_invoice()` creates temporary XLSX/PDF files and uploads the PDF
   outside database locks. Recheck the `PREPARING` claim/deadline in a short
   transaction, release locks, then send email.
4. `mark_simple_invoice_sent()` locks Employee then Invoice again, rechecks the
   claim/deadline, and stores the PDF reference with `SENT` atomically. Existing
   hour reservations remain linked.
5. Cancellation/expiry stops the task. Other exceptions attempt a guarded failure
   transition for the expected state, then propagate to Celery. Failure handling
   locks Employee before Invoice, releases hour links and clears the PDF reference;
   stale referenced files are deleted after commit. The task ignores results and
   has no automatic task retry.

The five-minute deadline is measured from `created_at`, not worker start or
`PREPARING`. At or beyond it, active invoices can become `FAILED` lazily during
submission, relevant work-hour updates, history/status/download checks or worker
guards. There is no dedicated five-minute periodic cleanup job. Overlap protection
is implemented by services serialized through Employee locks, not a PostgreSQL
exclusion constraint; writes bypassing these services do not get that guarantee.

PostgreSQL, Redis, Cloudinary and email are not one atomic transaction. In
particular, the provider may accept an email before a timeout or before final
database commit fails. Expiry during sending can leave a failed invoice after
email acceptance; a later resubmission may send a duplicate. `SENT` is not proof
of inbox delivery. No exactly-once email guarantee or provider reconciliation is
implemented. Uploaded-file cleanup preserves a persisted PDF reference, and skips
deletion when database state cannot be established, accepting possible orphan files.

## XLSX, PDF, Email and Infrastructure

- `simple_invoice_xlsx.py` fills `invoice_templates/simple-invoice.xlsx` with
  openpyxl. C6–C10 are forced to string type after assignment; untrusted text is
  not interpreted as a formula. E14/F14 stay numeric. Template line/subtotal/total
  formulas remain; Python writes GST `G27=G26*<gst>%` and WSBC `G28=G26*<wsbc>%`.
  LibreOffice evaluates spreadsheet formulas while converting to PDF.
- `simple_invoice_pdf.py` runs headless LibreOffice with a separate temporary
  user profile and a 180-second subprocess timeout. `LIBREOFFICE_PATH` selects
  the executable, falling back to `soffice`. Conversion failures omit raw process
  output/private command paths from their exception messages.
- `PrivateInvoiceCloudinaryStorage` explicitly stores invoice PDFs as private
  raw resources. Authorized downloads use signed attachment URLs valid for
  300 seconds; these links grant temporary access to their holder. Avatar and
  Cheat Sheet images use the configured default media storage instead.
- `simple_invoice_email.py` sends the local PDF attachment to
  `SIMPLE_INVOICE_RECIPIENT_EMAIL` and Employee email through `core.services.email`
  and the configured Anymail/Brevo backend. Branding uses the unique active
  CompanyProfile, or `DEFAULT_FROM_EMAIL` display name/address when none exists.
  The invoice task does not pass request language or use `translation.override()`;
  email rendering follows the worker's active/default language.
- Redis provides the configured Django data cache, Celery broker and RedBeat
  scheduler infrastructure. They are separate responsibilities/namespaces;
  invoice status and reservations live in PostgreSQL. Account views do not add
  their own Redis rate limiter. Cache configuration can fall back to LocMemCache.

## History, Downloads and Retention

`SimpleInvoiceHistoryView` lists only the current user's invoices created within
the rolling 36-month retention window, newest first. It expires stale active
invoices, then filters the retained list by invoice year or creation-time period
(3/6/12/24/36 months). Available years come from that retained list; there is no
pagination. `PREPARING` uses processing styling but its own localized status name.

`SimpleInvoiceStatusView` is AJAX GET only. Both status and
`SimpleInvoiceDownloadView` look up the owner's invoice and check expiry. Missing
or another user's IDs return 404. Download returns 409 unless `SENT` has a PDF;
otherwise it redirects to the signed Cloudinary URL. Work-hour update, period
preview, status and download endpoints use `never_cache`.

Celery Beat schedules `cleanup_expired_simple_invoices` on Sunday at 03:00 and
`cleanup_expired_work_hours` at 04:15 in the configured Celery timezone
(`America/Vancouver`). Invoice cleanup deletes records older than the rolling
36-month cutoff. Work-hour cleanup deletes dates before the first retained month
of the twelve-month window, including linked rows; it does not delete the Invoice.
Cleanup uses per-Employee transactions and Employee-before-Invoice locks.
`django-cleanup` handles stored-file removal on model deletion. Weekly physical
cleanup and the history window are distinct; cleanup requires running Beat/workers.

## Cheat Sheets and Cache Invalidation

`CheatSheetView` returns a cached guide list on full GET, or cached steps for
`cheat_sheet_id` on `partial=1`. Invalid/missing IDs produce an empty step list;
there is no separate detail-object 404 check. Admin edits translated guides/steps
and suggests the next step number. PostgreSQL enforces unique step numbers per guide.

Only evaluated data lists are cached, not HTML or unevaluated QuerySets:

- `account:cheat_sheets:list:<language>`, ordered by name;
- `account:cheat_sheet:steps:<id>:<language>`, ordered by step number.

Both use `CACHE_DEFAULT_TIMEOUT` (900 seconds by default), the active Django
language and the backend's configured key prefix. Save/delete signals schedule
targeted `delete_many()` for all `settings.LANGUAGES` after commit. Guide changes
invalidate the list and its steps; step changes invalidate the relevant steps;
moving a step invalidates old and new parents. Rollback keeps cached data.
`QuerySet.update()` and bulk writes bypass save signals. Concurrent cache fills
can restore stale data after invalidation; TTL bounds its lifetime. Redis
invalidation failures are logged and can leave stale content until expiry;
cache read failures have no dedicated fallback/503 handler here.

## Service Map and Diagnostics

| Module in `account/services/` | Responsibility |
| --- | --- |
| `work_hours.py` | Month selection, hour validation/writes, calendars and effective totals. |
| `simple_invoice_period.py` | Period eligibility, overlap checks, hour totals and reservations. |
| `simple_invoice_submission.py` | Transactional creation and post-commit task publication. |
| `simple_invoice_processing.py` | Locks, guarded state transitions, expiry and reservation release. |
| `simple_invoice_service.py` | File/email orchestration and uploaded-file cleanup. |
| `simple_invoice_xlsx.py`, `simple_invoice_pdf.py` | Template filling and LibreOffice conversion. |
| `simple_invoice_email.py` | Recipients, branding, attachment and shared email sender. |
| `cache.py` | Language-specific Cheat Sheet data caching and targeted invalidation. |

Account errors use the configured stderr handler (`propagate=False`) and
`EmailErrorFormatter`: exception type/traceback locations remain, provider
messages, chained exception details and locals are omitted. Source log messages
use invoice IDs and exception types rather than addresses, tokens or file contents.
`AccountTaskFailureFilter` redacts account task failure arguments/exception data in
`celery.app.trace`; `AccountCleanupFailureFilter` redacts account file failures
from `django_cleanup.handlers`. Celery reports propagated task errors; no second
generic task-error log is added. Logs are available in the relevant Render
web/worker service's Logs, subject to the configured logging level.

## Backend Checks

Follow [Isolated Backend Testing](../backend_testing.md) for PostgreSQL Docker
setup and runner safety. From the activated project environment:

```powershell
python manage.py test account.tests --settings=config.settings.test
python -m flake8 account
```

The 34 account backend tests passed on PostgreSQL in the main Erbauer repository,
as did Flake8. The suite covers invoice lifecycle/concurrency/publication,
work-hour access and period rules, profile validation, XLSX formula protection,
cache commit/rollback invalidation and log redaction. External email, Cloudinary,
Celery publication and LibreOffice boundaries are mocked. These tests need no
real Redis opt-in, worker or production credentials; they do not establish actual
provider delivery, Cloudinary permissions or LibreOffice rendering in deployment.
