from math import ceil
from time import time
from django.core.cache import cache
from django.utils.translation import ngettext

from core.utils.request import get_client_ip_key

REGISTRATION_COOLDOWN_PREFIX = "registration_ip_cooldown"
REGISTRATION_ATTEMPTS_PREFIX = "registration_ip_attempts"


def _cooldown_key(client_id: str) -> str:
    return f"{REGISTRATION_COOLDOWN_PREFIX}_{client_id}"


def _attempts_key(client_id: str) -> str:
    return f"{REGISTRATION_ATTEMPTS_PREFIX}_{client_id}"


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


def get_registration_state(request) -> dict:
    client_ip = get_client_ip_key(request)
    cooldown_key = _cooldown_key(client_ip)

    return {
        "client_ip": client_ip,
        "cooldown_key": cooldown_key,
        "attempts_key": _attempts_key(client_ip),
        "remaining_minutes": _remaining_minutes(cooldown_key),
    }


def is_blocked(request) -> tuple[bool, int]:
    state = get_registration_state(request)
    remaining_minutes = state["remaining_minutes"]
    return remaining_minutes > 0, remaining_minutes


def registration_attempt(
    *,
    request,
    attempts_limit: int,
    cooldown_seconds: int,
) -> None:
    state = get_registration_state(request)

    attempts = _increment_attempts(
        state["attempts_key"],
        cooldown_seconds,
    )

    if attempts >= attempts_limit:
        _start_cooldown(state["cooldown_key"], cooldown_seconds)
        _reset_attempts(state["attempts_key"])


def cooldown_message(remaining_minutes: int) -> str:
    return ngettext(
        "Too many registration attempts. Please try again in %(minutes)s minute.",
        "Too many registration attempts. Please try again in %(minutes)s minutes.",
        remaining_minutes,
    ) % {"minutes": remaining_minutes}
