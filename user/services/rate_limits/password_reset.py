from django.conf import settings
from django.http import HttpRequest
from django.utils.translation import gettext as _, ngettext

from core.services.rate_limit import (
    RateLimitField,
    RateLimitState,
    get_rate_limit_state,
    register_rate_limit_attempt,
)
from core.utils.request import get_client_ip_key

SCOPE = "user_password_reset"
ATTEMPTS = settings.PASSWORD_RESET_ATTEMPTS
WINDOW_SECONDS = settings.PASSWORD_RESET_WINDOW
COOLDOWN_SECONDS = settings.PASSWORD_RESET_COOLDOWN


def get_password_reset_rate_limit_state(
    request: HttpRequest,
    email: str,
) -> RateLimitState:
    ip = get_client_ip_key(request)
    return get_rate_limit_state(
        scope=SCOPE,
        fields=[
            RateLimitField(name="ip", value=ip),
            RateLimitField(name="email", value=email),
            RateLimitField(name="captcha_ip", value=ip),
        ],
        attempts_limit=ATTEMPTS,
    )


def register_password_reset_attempt(
    request: HttpRequest,
    email: str,
) -> RateLimitState:
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


def register_password_reset_captcha_failure(request: HttpRequest) -> RateLimitState:
    """Count failed CAPTCHA only against its separate IP counter."""
    return register_rate_limit_attempt(
        scope=SCOPE,
        fields=[RateLimitField(name="captcha_ip", value=get_client_ip_key(request))],
        attempts_limit=ATTEMPTS,
        window_seconds=WINDOW_SECONDS,
        cooldown_seconds=COOLDOWN_SECONDS,
    )


def get_password_reset_cooldown_message(state: RateLimitState) -> str:
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

    return _("Too many password reset requests. Please try again in %(time)s.") % {
        "time": " ".join(parts),
    }
