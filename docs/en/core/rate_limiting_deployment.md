# Shared Rate Limiting Deployment

These are deployment requirements. Passing local automated tests does not
confirm the security of the deployed Render ingress.

## IP Source

- Local: `CLIENT_IP_SOURCE=remote_addr` (also the default value).
- Render Free and Paid, public ingress: `CLIENT_IP_SOURCE=render_cloudflare`.
- X-Forwarded-For is not used. A missing or invalid address returns
  `None`, and the rate limiting key is `no-ip`.

One implementation serves both plans. The mode is not selected automatically
based on the plan, domain, or DEBUG. `config/settings/base.py` reads
`CLIENT_IP_SOURCE` through `os.getenv` after loading dotenv. Existing environment
variables take precedence: `load_dotenv` is called without `override=True`.
An unsupported value raises ImproperlyConfigured when determining the IP.

The `.env.example` file provides the local value `remote_addr`. For local
execution, use `config.settings.dev` with a configured Redis connection:
`config.settings.base` itself does not configure a Redis cache. The maintainer
configures files containing real secrets separately.

For Render Free, set `CLIENT_IP_SOURCE=render_cloudflare` in the service's
Environment. Use the same value for Paid with a custom domain. For both,
use `config.settings.prod` and the existing `REDIS_URL`; the limiter does not
need a separate Redis URL. Verify the deployment after changing settings.

Trusting CF-Connecting-IP is allowed only when untrusted requests are guaranteed
to pass through the Render/Cloudflare public ingress that overwrites this
header. The header alone does not prove the origin of a request.

On Paid, check private-network access. The absence of planned private calls
does not technically block them. Untrusted services must not have private
HTTP access to Django. Isolation between environments does not isolate services
within a single environment. If this boundary cannot be enforced, do not
consider render_cloudflare protected against private spoofing: first resolve
network isolation or establish a verified way to distinguish ingress routes.

The custom domain and onrender.com must be checked separately by supplying XFF
and CF-Connecting-IP in controlled requests. Forwarded headers are always ignored
locally. Do not enable trust merely because a request contains CF-Connecting-IP.
Moving from Free to Paid requires rechecking private accessibility, even if
the code and CLIENT_IP_SOURCE value remain unchanged.

## Redis

The limiter uses RedisCache from CACHES.default and its existing pool.
It does not create a separate URL or pool. LocMem is not a fallback for the
limiter: without Redis, protected requests return 503. Other cache mechanisms
are unchanged.

Upstash supports EVAL/EVALSHA. Check the specific user's permissions, Lua
limits, quotas, eviction, and socket/connect timeouts of the current cache
connection. The limiter does not change shared pool settings. Ambiguous
execution timeouts are not retried; NOSCRIPT allows EVAL because the script
has not executed yet.

Expected limiter failures are handled by a shared CBV mixin. Contact returns
an HTML partial containing the populated form and HTTP 503; authentication
views return a standalone 503 page. Rendering these responses does not pass
request to render_to_string, avoiding cache-dependent context processors.
The 503 page uses local Bootstrap and errors.css, does not inherit base.html,
and does not read the company profile. The protected operation does not
continue. Script/data-format errors that the implementation recognizes as
defects are not replaced with a network error message.

The rate_limit:v2 keys contain numeric values, not pickled dictionaries.
Django applies the prefix and version. After the transition, limits from the
old namespace are not migrated, and old keys expire according to their TTL.
Do not clear Redis.

Only fields with nonempty normalized values participate in these operations.
Window retains inactivity semantics: registering an attempt below the threshold,
when none of the supplied fields is blocked, increments every supplied field's
counter and renews its window TTL. This is not an exact sliding window.
Reading the state does not change counters or TTLs.

When any field reaches the threshold, that registration returns a blocked state,
sets blocking keys for all supplied fields for the configured cooldown, and
deletes their attempt counters. While any supplied field remains blocked,
registration returns the existing block without incrementing counters or renewing
the window TTL or cooldown. Blocked requests therefore do not extend cooldown.
Reset deletes the attempt and blocking keys only for the supplied scope and fields.

Registration of all fields and blocking are atomic within one Lua invocation;
the entire HTTP workflow does not become a Redis transaction. Thresholds,
scopes, and configured window/cooldown durations remain unchanged.

## Verification Status and Deployment Checks

The maintainer has confirmed successful runs of 81 ordinary backend tests and
8 opt-in Redis integration tests in the isolated local environment. The ordinary
tests cover contact workflows and shared rate limiting, including NOSCRIPT,
storage failures, and protection against replay after ambiguous timeouts.
The Redis integration tests exercise real Lua: threshold blocking across fields,
window TTL renewal and expiry, reads without TTL renewal, cooldown expiry,
blocked requests without cooldown extension, scoped reset, and concurrent requests.

These results do not replace deployment checks of Render public ingress,
the custom domain, onrender.com, private-network accessibility, or the current
Upstash permissions, limits, and timeouts. Full authentication/Turnstile workflow
regressions require separate verification; the main/core test runs do not confirm
coverage of all user application workflows.

Tests must not use development or production caches, brokers, or Redis.
Only the isolated local Docker Redis is used for opt-in Redis integration tests;
external email providers and real Celery workers are not used. New translations
must still be extracted and compiled in the development environment when added.
This documentation update did not rerun tests, deployment checks, or translation
commands.
