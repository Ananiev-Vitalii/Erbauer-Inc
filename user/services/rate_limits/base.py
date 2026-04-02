from math import ceil
from time import time
from django.core.cache import cache
from django.utils.translation import ngettext

from core.utils.request import get_client_ip_key


def _email_cooldown_key(namespace: str, email: str) -> str:
    return f"{namespace}_email_cooldown_{email.lower()}"


def _client_cooldown_key(namespace: str, client_id: str) -> str:
    return f"{namespace}_client_cooldown_{client_id}"


def _email_attempts_key(namespace: str, email: str) -> str:
    return f"{namespace}_email_attempts_{email.lower()}"


def _client_attempts_key(namespace: str, client_id: str) -> str:
    return f"{namespace}_client_attempts_{client_id}"


def _start_cooldown(key: str, timeout: int) -> None:
    expires_at = int(time()) + timeout
    cache.set(key, expires_at, timeout=timeout)


def _remaining_seconds(key: str) -> int:
    expires_at = cache.get(key)
    if not expires_at:
        return 0

    remaining_seconds = int(expires_at - time())
    return max(0, remaining_seconds)


def _remaining_minutes(key: str) -> int:
    remaining_seconds = _remaining_seconds(key)
    if remaining_seconds <= 0:
        return 0
    return max(1, ceil(remaining_seconds / 60))


def _attempts_count(key: str) -> int:
    return int(cache.get(key, 0))


def _increment_attempts(key: str, timeout: int) -> int:
    attempts = _attempts_count(key) + 1
    cache.set(key, attempts, timeout=timeout)
    return attempts


def _reset_attempts(key: str) -> None:
    cache.delete(key)


def get_rate_limit_state(*, request, email: str, namespace: str) -> dict:
    client_id = get_client_ip_key(request)

    email_cooldown_key = _email_cooldown_key(namespace, email)
    client_cooldown_key = _client_cooldown_key(namespace, client_id)

    email_remaining = _remaining_minutes(email_cooldown_key)
    client_remaining = _remaining_minutes(client_cooldown_key)
    remaining_minutes = max(email_remaining, client_remaining)

    return {
        "client_id": client_id,
        "email_cooldown_key": email_cooldown_key,
        "client_cooldown_key": client_cooldown_key,
        "email_attempts_key": _email_attempts_key(namespace, email),
        "client_attempts_key": _client_attempts_key(namespace, client_id),
        "remaining_minutes": remaining_minutes,
    }


def register_rate_limit_attempt(
        *,
        request,
        email: str,
        namespace: str,
        attempts_limit: int,
        cooldown_seconds: int,
) -> None:
    state = get_rate_limit_state(
        request=request,
        email=email,
        namespace=namespace,
    )

    email_attempts = _increment_attempts(
        state["email_attempts_key"],
        cooldown_seconds,
    )
    client_attempts = _increment_attempts(
        state["client_attempts_key"],
        cooldown_seconds,
    )

    if email_attempts >= attempts_limit or client_attempts >= attempts_limit:
        _start_cooldown(state["email_cooldown_key"], cooldown_seconds)
        _start_cooldown(state["client_cooldown_key"], cooldown_seconds)
        _reset_attempts(state["email_attempts_key"])
        _reset_attempts(state["client_attempts_key"])


def get_rate_limit_cooldown_message(remaining_minutes: int) -> str:
    return ngettext(
        "Too many requests. Please try again in %(minutes)s minute.",
        "Too many requests. Please try again in %(minutes)s minutes.",
        remaining_minutes,
    ) % {"minutes": remaining_minutes}
