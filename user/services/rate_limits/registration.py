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

SCOPE = "user_registration"
ATTEMPTS = settings.REGISTRATION_ATTEMPTS
WINDOW_SECONDS = settings.REGISTRATION_WINDOW
COOLDOWN_SECONDS = settings.REGISTRATION_COOLDOWN


def get_registration_rate_limit_state(request: HttpRequest) -> RateLimitState:
    return get_rate_limit_state(
        scope=SCOPE,
        fields=[RateLimitField(name="ip", value=get_client_ip_key(request))],
        attempts_limit=ATTEMPTS,
    )


def register_registration_attempt(request: HttpRequest) -> RateLimitState:
    return register_rate_limit_attempt(
        scope=SCOPE,
        fields=[RateLimitField(name="ip", value=get_client_ip_key(request))],
        attempts_limit=ATTEMPTS,
        window_seconds=WINDOW_SECONDS,
        cooldown_seconds=COOLDOWN_SECONDS,
    )


def get_registration_cooldown_message(state: RateLimitState) -> str:
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

    return _("Too many registration attempts. Please try again in %(time)s.") % {
        "time": " ".join(parts),
    }
