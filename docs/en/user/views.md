# User View Algorithms

Routes are registered under `/accounts/` in `user/urls.py`. Read-only pages use
GET; forms use GET/POST. Validation and cooldown responses normally render HTML
with status 200. Expected Redis failures stop protected processing with 503 via
`RateLimitUnavailableMixin`. Normal CSRF middleware still applies to POSTs.

## Registration — UserRegistrationView

1. Redirect authenticated visitors home. On POST, check `user_registration`
   blocking by trusted IP before form validation or Turnstile.
2. Validate email, passwords and required consent. The form finds an active,
   unlinked Employee using database `LOWER(email)` and rejects existing users.
3. Verify CAPTCHA. Invalid forms and failed CAPTCHA count one IP attempt through
   `form_invalid()`; successful registration does not add an attempt.
4. Prepare an unsaved User with the Django creation form. Call
   `user.services.registration.register_employee_user()`.
5. The service locks Employee inside `atomic()`, rechecks activity, email and
   linkage, then saves User (inactive/unverified), the Employee link and Profile.
   It preserves Employee email spelling and copies employee names. PostgreSQL
   email uniqueness is the final protection against concurrent inserts.
6. Expected eligibility/email conflicts become `RegistrationConflict`, then a
   bound form error. Only known User email uniqueness constraints with SQLSTATE
   23505 are translated after rollback; unrelated database errors propagate.
7. The service schedules the supplied callback with `on_commit()`. The view's
   callback sends verification mail and adds a warning if delivery fails.
   Redirect to `user:confirm_user`; committed records are retained on email failure.

The service accepts Employee ID, a prepared User and a callback, not request,
form or messages. Outer transactions defer the callback; rollback discards it.

## Login — LoginUser

1. Check `user_login` blocking for `ip`, `email`, `captcha_ip` before Turnstile.
2. Verify CAPTCHA and recheck blocking to account for concurrent requests.
3. Failed CAPTCHA counts only `captcha_ip` once. Render directly, avoiding
   `form_invalid()`. Blocked/failed-CAPTCHA forms use `allow_authentication=False`:
   even lazy form validation during rendering cannot invoke authentication.
4. After successful CAPTCHA, use normal Django authentication. Invalid credentials
   count `[ip, email]` once. On success, reset all three limiter fields before
   Django creates the authenticated session and performs its safe redirect.

Password widgets do not redisplay submitted passwords. Reset failure returns 503
before login. Registration and login intentionally do not use the email-request mixin.

## Resend — ConfirmUser

1. Redirect authenticated visitors home. `RateLimitedTurnstileMixin` checks
   `ip`, `email`, `captcha_ip` in `user_resend_verification` before validation/Turnstile.
2. Validate the form, verify CAPTCHA, then recheck blocking. Failed CAPTCHA adds
   only a `captcha_ip` attempt; successful CAPTCHA adds one business attempt for
   `[ip, email]`. Threshold-reaching requests do not continue to email delivery.
3. Find only inactive, unverified users by database-lowered email. Send through
   the existing email service if eligible; return the same neutral success form
   for missing/ineligible users or expected delivery failure.

The mixin's failure path does not add attempts in `form_invalid()`. Existing
blocks are read without renewing cooldown. Separate CAPTCHA counters prevent
invalid CAPTCHA from consuming another person's email quota; shared IP users
still share the IP restriction. Existing business email limits remain in effect.

## Verification — verify_user / InvalidVerify

GET verification remains intentional. Inside `atomic()`, decode UID and lock User
before checking the token. Only `is_active=False, is_verified=False` can become
True/True and log in. The second concurrent request sees updated state and cannot
reuse the original token. Invalid/expired/used tokens redirect to `invalid_verify`;
valid tokens for ineligible states do not activate or log in, and redirect home.
`InvalidVerify` simply renders the failure page. Employee status is not changed.

## Password reset — CustomPasswordResetView and standard views

The same mixin algorithm as resend applies under `user_password_reset`, with its
own thresholds and counters. After the gate, add company branding and delegate
token generation/email to Django. `CustomPasswordResetForm.get_users()` selects
active users with usable passwords using database-lowered email. Django handles
delivery exceptions and logs them; no duplicate exception wrapper is added.
Successful submission redirects to `password-reset-done`. Confirm uses Django's
`PasswordResetConfirmView` and `CustomSetPasswordForm`; invalid links show the
standard invalid-link result, and a successful change redirects to
`password-reset-complete`. Done/complete views only render information pages.

## Logout and email infrastructure

Logout uses Django's POST `LogoutView` and redirects home. No custom logout
service is needed. Anonymous-only restrictions apply to registration, resend and
reset request; login redirects authenticated users through Django's LoginView.

Verification email uses request host/protocol and the existing token format.
`send_verification_email()` logs Anymail API/recipient and requests transport
failures, returning False; programming/configuration errors are not swallowed.
Branding uses the unique active CompanyProfile, or the configured
`DEFAULT_FROM_EMAIL` display name/address. PostgreSQL permits zero or one active
profile. Email ERROR logs go to stderr with sanitized traceback locations and
exception class, without exception payloads, chains or locals. No Celery/retries
are introduced. See [shared limiter deployment](../core/rate_limiting_deployment.md)
for trusted IP and Redis requirements.
