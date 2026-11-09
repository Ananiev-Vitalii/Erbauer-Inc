# Main Views

This guide describes the views registered in `main/urls.py`. The four custom
classes are in `main/views.py`; Privacy Policy uses Django's `TemplateView`
directly in the URL configuration. All are public; none requires login.

## Shared Request Context

The read-only pages below handle GET and standard HEAD/OPTIONS requests;
unsupported methods return 405. Their normal template rendering runs global
context processors. In particular, `main.context_processors.company_base` loads
language-specific cached company data and, for an authenticated user, queries
`account.Profile` through `employee__user`. Anonymous users have no profile query.
Contact partials explicitly bypass these processors.

Django's active language controls translations and data-cache keys. Routes are
not language-prefixed in the current `config/urls.py`. Cache services use
`CACHE_DEFAULT_TIMEOUT` (900 seconds by default); normal cache misses load data
through the ORM. Save/delete signals for CompanyProfile, Service, Project,
TeamMember, Employee and Position schedule invalidation after transaction commit.
This does not cover `QuerySet.update()` or bulk writes that bypass save signals.

## HomePageView

**Purpose / request:** Render the home page at GET `/` (`main:home`).

1. Load services, visible team members, the active company profile and the latest
   four projects through the language-specific data-cache services.
2. On cache misses, select the newest active company profile, order services by
   title and projects by descending ID. Load visible team members in display
   order, joining their employee and position through `select_related()`.
3. Split services into groups of six (`service_pages`). Set
   `has_more_team_members` when the loaded list contains more than four members;
   the view still passes the complete visible team list.
4. Add an unbound `ContactForm` and render `main/home.html` with the prepared
   context and the shared context above.

**Results:** Normally 200. Missing company data produces `None`, and empty
collections remain empty. No contact attempt or email task is created. There is
no HTML fragment cache; the view calls the data-cache services on every request.
Cache/ORM failures here have no dedicated 503 handler.

## ContactFormView

**Purpose / request:** Process POST `/contact/submit/`
(`main:contact_submit`) and return the contact form HTML partial. GET and other
methods, including HEAD/OPTIONS, return 405. Standard CSRF middleware still
applies; a rejected CSRF check returns 403 before form processing.

1. Read the IP-based limiter state for scope `main_contact_form`. IP selection
   follows `CLIENT_IP_SOURCE`; a missing or invalid selected IP uses `no-ip`.
2. If already blocked, return a bound form containing the submitted data and a
   localized cooldown message. Otherwise register an attempt atomically in Redis.
   If this reaches the threshold, return the same kind of bound response.
3. Only when allowed, validate `ContactForm`: required name, phone, message and
   Privacy Policy consent, length limits and the accepted phone formats. The form
   normalizes a valid phone to `+1XXXXXXXXXX`. Invalid forms return bound with
   their validation errors. Invalid submissions count as attempts too.
4. For a valid form, publish `send_contact_email_task` with only cleaned `name`,
   `phone`, `message` and the active language. Task argument representation is
   redacted and publishing retry is disabled. No request object is passed.
5. If publishing raises Kombu `OperationalError`, return the bound form with a
   localized technical error. On successful publishing, return a fresh form with
   `is_success=True`. This confirms submission, not email delivery.
6. Render `main/includes/sections/contacts.html#contact-form`, including the
   `data-contact-form-response` marker. Inject a CSRF token using `get_token()`
   and call `render_to_string()` without a request: global context processors
   do not run. Return HTML with the supplied response status/options (normally
   200), retaining a token suitable for the next POST.

**Results:** Validation errors, cooldown, broker publishing failure and success
all normally return 200, not 429 or a redirect. Expected Redis failures become
`RateLimitUnavailable`; the shared mixin stops processing and returns a bound
partial with a localized error, CSRF token and HTTP 503, also without global
context processors. Unhandled programming/provider errors are not converted to
success. The view does not reset the limiter after a successful submission.

**Background continuation:** The Celery task uses `translation.override(language)`
and calls `main.services.email.send_contact_email`. That service queries the
active company name, prepares `main/contact_email.html`, and calls the shared
HTML email service for `COMPANY_CONTACT_EMAIL`. The configured email backend
performs delivery. Exceptions propagate to Celery; the task ignores results and
does not configure automatic retry. Delivery failure cannot change the HTTP
response already returned. No contact request is stored in the database.

## ProjectListView

**Purpose / request:** Render GET `/projects/` (`main:project_list`).

1. Read `category`. Accept `residential` or `commercial` from
   `ProjectCategory.values`; missing or unsupported values select `all`.
2. Build the Project queryset, filter by category when selected, and retain the
   model's descending-ID ordering. This view does not use the home-page cache.
3. Apply Django pagination with six projects per page using the `page` parameter.
4. Add `current_category` to the standard list/pagination context, expose the
   page's objects as `projects`, and render `main/project_list.html`.

**Results:** Normally 200, including an empty first page. Invalid/out-of-range
pages return 404; Django's standard `page=last` value is supported. An unsupported
category falls back to all projects rather than returning an error.

## ProjectDetailView

**Purpose / request:** Render GET `/projects/<int:pk>/`
(`main:project_detail`).

1. Look up the Project by primary key using the ORM.
2. Prefetch its `images` collection to avoid individual gallery queries.
3. Expose the object as `project` and render `main/project_detail.html` with the
   shared context. No home-page data-cache service is used for this lookup.

**Results:** 200 for an existing project, including one with no gallery images;
404 when no project matches. The URL converter rejects non-integer path values.

## Privacy Policy TemplateView

**Purpose / request:** Render GET `/privacy_policy/` (`main:privacy_policy`).

1. The URL configuration supplies `main/privacy_policy.html` and
   `privacy_policy_updated_on=date(2026, 11, 7)` through `extra_context`.
2. Render the document with the shared context. The template uses the same fixed
   date object in either language, localized with `DATE_FORMAT`, and an ISO date
   in the semantic `time` element.

**Results:** Normally 200. There is no document-model lookup, date calculation
from today's date, form submission or background task. Shared context processors
can still access the company cache and authenticated user's profile.
