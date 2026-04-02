from user.services.rate_limits.base import (
    get_rate_limit_cooldown_message,
    get_rate_limit_state,
    register_rate_limit_attempt,
)

NAMESPACE = "password_reset"


def get_password_reset_state(request, email: str) -> dict:
    return get_rate_limit_state(
        request=request,
        email=email,
        namespace=NAMESPACE,
    )


def register_password_reset_attempt(
        *,
        request,
        email: str,
        attempts_limit: int,
        cooldown_seconds: int,
) -> None:
    register_rate_limit_attempt(
        request=request,
        email=email,
        namespace=NAMESPACE,
        attempts_limit=attempts_limit,
        cooldown_seconds=cooldown_seconds,
    )


def get_password_reset_cooldown_message(remaining_minutes: int) -> str:
    return get_rate_limit_cooldown_message(remaining_minutes)
