from django.conf import settings
from django.http import HttpRequest
from django.utils.translation import gettext as _, ngettext

from core.services.rate_limit import (
    RateLimitField,
    RateLimitState,
    get_rate_limit_state,
    register_rate_limit_attempt,
    reset_rate_limit,
)
from core.utils.request import get_client_ip_key

SCOPE = "user_login"
ATTEMPTS = settings.LOGIN_ATTEMPTS
WINDOW_SECONDS = settings.LOGIN_WINDOW
COOLDOWN_SECONDS = settings.LOGIN_COOLDOWN


def get_login_identifier(request: HttpRequest) -> str:
    return (request.POST.get("username") or "").strip().casefold()


def get_login_rate_limit_state(request: HttpRequest) -> RateLimitState:
    email = get_login_identifier(request)

    return get_rate_limit_state(
        scope=SCOPE,
        fields=[
            RateLimitField(name="ip", value=get_client_ip_key(request)),
            RateLimitField(name="email", value=email),
        ],
        attempts_limit=ATTEMPTS,
    )


def register_login_attempt(request: HttpRequest) -> RateLimitState:
    email = get_login_identifier(request)

    return register_rate_limit_attempt(
        scope=SCOPE,
        fields=[
            RateLimitField(name="ip", value=get_client_ip_key(request)),
            RateLimitField(name="email", value=email),
        ],
        attempts_limit=ATTEMPTS,
        window_seconds=WINDOW_SECONDS,
        cooldown_seconds=COOLDOWN_SECONDS,
    )


def reset_login_rate_limit(request: HttpRequest) -> None:
    email = get_login_identifier(request)

    reset_rate_limit(
        scope=SCOPE,
        fields=[
            RateLimitField(name="ip", value=get_client_ip_key(request)),
            RateLimitField(name="email", value=email),
        ],
    )


def get_login_cooldown_message(state: RateLimitState) -> str:
    minutes = state.remaining_seconds // 60
    seconds = state.remaining_seconds % 60

    parts = []

    if minutes > 0:
        parts.append(
            ngettext(
                "%(count)d minute",
                "%(count)d minutes",
                minutes,
            )
            % {"count": minutes}
        )

    if seconds > 0:
        parts.append(
            ngettext(
                "%(count)d second",
                "%(count)d seconds",
                seconds,
            )
            % {"count": seconds}
        )

    return _("Too many failed login attempts. Please wait %(time)s and try again.") % {
        "time": " ".join(parts),
    }
