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

RESEND_VERIFICATION_SCOPE = "user_resend_verification"
RESEND_VERIFICATION_ATTEMPTS = settings.VERIFICATION_ATTEMPTS
RESEND_VERIFICATION_WINDOW_SECONDS = settings.VERIFICATION_WINDOW
RESEND_VERIFICATION_COOLDOWN_SECONDS = settings.VERIFICATION_COOLDOWN


def get_resend_verification_rate_limit_state(
    request: HttpRequest,
    email: str,
) -> RateLimitState:
    return get_rate_limit_state(
        scope=RESEND_VERIFICATION_SCOPE,
        fields=[
            RateLimitField(name="ip", value=get_client_ip_key(request)),
            RateLimitField(name="email", value=email),
        ],
        attempts_limit=RESEND_VERIFICATION_ATTEMPTS,
    )


def register_resend_verification_attempt(
    request: HttpRequest,
    email: str,
) -> RateLimitState:
    return register_rate_limit_attempt(
        scope=RESEND_VERIFICATION_SCOPE,
        fields=[
            RateLimitField(name="ip", value=get_client_ip_key(request)),
            RateLimitField(name="email", value=email),
        ],
        attempts_limit=RESEND_VERIFICATION_ATTEMPTS,
        window_seconds=RESEND_VERIFICATION_WINDOW_SECONDS,
        cooldown_seconds=RESEND_VERIFICATION_COOLDOWN_SECONDS,
    )


def get_resend_verification_cooldown_message(state: RateLimitState) -> str:
    minutes = state.remaining_seconds // 60
    seconds = state.remaining_seconds % 60

    parts = []

    if minutes > 0:
        parts.append(
            ngettext("%(count)d minute", "%(count)d minutes", minutes)
            % {"count": minutes}
        )

    if seconds > 0:
        parts.append(
            ngettext("%(count)d second", "%(count)d seconds", seconds)
            % {"count": seconds}
        )

    return _("Too many verification email requests. Please try again in %(time)s.") % {
        "time": " ".join(parts),
    }


def get_resend_verification_success_message() -> str:
    return _(
        "If this email address is associated with an unverified account, "
        "we have sent a new verification email."
    )
