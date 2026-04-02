from datetime import timedelta
from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_client_ip_address
from axes.utils import reset
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, ngettext

LAST_LOGIN_EMAIL_SESSION_KEY = "last_login_email"


def get_normalized_username(request, use_session_fallback=False):
    username = (request.POST.get("username") or "").strip().lower()
    if username:
        return username

    if use_session_fallback:
        return (request.session.get(LAST_LOGIN_EMAIL_SESSION_KEY) or "").strip().lower()

    return ""


def remember_login_email(request):
    username = get_normalized_username(request)
    if username:
        request.session[LAST_LOGIN_EMAIL_SESSION_KEY] = username
    return username


def clear_login_email(request):
    request.session.pop(LAST_LOGIN_EMAIL_SESSION_KEY, None)


def get_client_ip(request):
    return get_client_ip_address(request) or ""


def get_lock_cache_keys(request):
    keys = []

    ip = get_client_ip(request)
    if ip:
        keys.append(f"login_lockout_ip:{ip}")

    username = get_normalized_username(request, use_session_fallback=True)
    if username:
        keys.append(f"login_lockout_email:{username}")

    return keys


def get_cache_deadline(key):
    raw = cache.get(key)
    if not raw:
        return None

    try:
        dt = timezone.datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        cache.delete(key)
        return None

    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())

    return dt


def set_cache_deadline(key, until):
    cache.set(key, until.isoformat(), timeout=24 * 60 * 60)


def clear_cache_deadlines(request):
    for key in get_lock_cache_keys(request):
        cache.delete(key)


def get_active_deadline(request):
    deadlines = [get_cache_deadline(key) for key in get_lock_cache_keys(request)]
    deadlines = [dt for dt in deadlines if dt is not None]
    return max(deadlines) if deadlines else None


def reset_axes_attempts(request):
    username = get_normalized_username(request, use_session_fallback=True)
    ip_address = get_client_ip(request)

    if username:
        reset(username=username)

    if ip_address:
        reset(ip=ip_address)


def full_reset_lockout_state(request):
    reset_axes_attempts(request)
    clear_cache_deadlines(request)


def start_fixed_lockout(request):
    current_deadline = get_active_deadline(request)
    now = timezone.now()

    if current_deadline and current_deadline > now:
        return current_deadline

    until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)

    for key in get_lock_cache_keys(request):
        set_cache_deadline(key, until)

    reset_axes_attempts(request)
    return until


def build_lockout_message(seconds_left):
    minutes = seconds_left // 60
    seconds = seconds_left % 60
    parts = []

    if minutes:
        parts.append(
            ngettext("%(count)d minute", "%(count)d minutes", minutes)
            % {"count": minutes}
        )

    if seconds:
        parts.append(
            ngettext("%(count)d second", "%(count)d seconds", seconds)
            % {"count": seconds}
        )

    return _("Too many failed login attempts. Please wait %(time)s and try again.") % {
        "time": " ".join(parts)
    }


def build_locked_response(deadline, now=None):
    now = now or timezone.now()
    seconds_left = max(0, int((deadline - now).total_seconds()))
    return {
        "is_locked": True,
        "seconds": seconds_left,
        "message": build_lockout_message(seconds_left),
    }


def get_lockout_data(request):
    now = timezone.now()
    deadline = get_active_deadline(request)

    if deadline and deadline <= now:
        full_reset_lockout_state(request)
        deadline = None

    if deadline:
        return build_locked_response(deadline, now)

    username = get_normalized_username(request, use_session_fallback=True)
    if username and AxesProxyHandler.is_locked(
        request, credentials={"username": username}
    ):
        deadline = start_fixed_lockout(request)
        return build_locked_response(deadline, now)

    return {
        "is_locked": False,
        "seconds": 0,
        "message": "",
    }


def is_locked_after_failed_login(request):
    username = get_normalized_username(request)
    if not username:
        return False

    return AxesProxyHandler.is_locked(request, credentials={"username": username})
