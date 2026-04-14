from django.conf import settings
from django.http import HttpRequest
from django.utils.translation import ngettext, gettext as _

from core.services.rate_limit import (
    RateLimitField,
    RateLimitState,
    get_rate_limit_state,
    register_rate_limit_attempt,
)
from core.utils.request import get_client_ip_key

SCOPE = "main_contact_form"
ATTEMPTS = settings.CONTACT_FORM_ATTEMPTS
WINDOW_SECONDS = settings.CONTACT_FORM_WINDOW
COOLDOWN_SECONDS = settings.CONTACT_FORM_COOLDOWN


def get_contact_form_rate_limit_state(request: HttpRequest) -> RateLimitState:
    return get_rate_limit_state(
        scope=SCOPE,
        fields=[RateLimitField(name="ip", value=get_client_ip_key(request))],
        attempts_limit=ATTEMPTS,
    )


def register_contact_form_attempt(request: HttpRequest) -> RateLimitState:
    return register_rate_limit_attempt(
        scope=SCOPE,
        fields=[RateLimitField(name="ip", value=get_client_ip_key(request))],
        attempts_limit=ATTEMPTS,
        window_seconds=WINDOW_SECONDS,
        cooldown_seconds=COOLDOWN_SECONDS,
    )


def get_contact_form_cooldown_message(state: RateLimitState) -> str:
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

    return _("Too many attempts. Please try again in %(time)s.") % {
        "time": " ".join(parts),
    }
