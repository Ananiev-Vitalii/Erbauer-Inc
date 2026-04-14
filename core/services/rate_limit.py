from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from time import time
from typing import Iterable

from django.core.cache import cache


@dataclass(frozen=True)
class RateLimitField:
    name: str
    value: str | int | None


@dataclass(frozen=True)
class RateLimitState:
    blocked: bool
    remaining_seconds: int
    remaining_minutes: int
    attempts_limit: int
    triggered_by: str | None = None


def _normalize_value(value: str | int | None) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()


def _attempt_key(scope: str, field_name: str, field_value: str) -> str:
    return f"rate_limit:{scope}:attempt:{field_name}:{field_value}"


def _block_key(scope: str, field_name: str, field_value: str) -> str:
    return f"rate_limit:{scope}:block:{field_name}:{field_value}"


def get_rate_limit_state(
    *,
    scope: str,
    fields: Iterable[RateLimitField],
    attempts_limit: int,
) -> RateLimitState:
    """
    Check whether the current request scope is blocked.

    A scope is considered blocked if any tracked field still has an active cooldown.
    """
    matched_trigger: str | None = None
    max_remaining_seconds = 0
    now = int(time())

    for field in fields:
        normalized = _normalize_value(field.value)
        if not normalized:
            continue

        block_data = cache.get(_block_key(scope, field.name, normalized))
        if not block_data:
            continue

        blocked_until = int(block_data.get("blocked_until", 0))
        remaining_seconds = max(0, blocked_until - now)

        if remaining_seconds > max_remaining_seconds:
            max_remaining_seconds = remaining_seconds
            matched_trigger = field.name

    return RateLimitState(
        blocked=max_remaining_seconds > 0,
        remaining_seconds=max_remaining_seconds,
        remaining_minutes=ceil(max_remaining_seconds / 60) if max_remaining_seconds > 0 else 0,
        attempts_limit=attempts_limit,
        triggered_by=matched_trigger,
    )


def register_rate_limit_attempt(
    *,
    scope: str,
    fields: Iterable[RateLimitField],
    attempts_limit: int,
    window_seconds: int,
    cooldown_seconds: int,
) -> RateLimitState:
    """
    Register a failed attempt for all provided fields.

    Behavior:
    - each field has its own rolling window counter
    - if any field reaches the limit, cooldown is activated for all provided fields
    - all counters are then reset
    """
    normalized_fields: list[tuple[str, str]] = []

    for field in fields:
        normalized_value = _normalize_value(field.value)
        if not normalized_value:
            continue
        normalized_fields.append((field.name, normalized_value))

    if not normalized_fields:
        return RateLimitState(
            blocked=False,
            remaining_seconds=0,
            remaining_minutes=0,
            attempts_limit=attempts_limit,
            triggered_by=None,
        )

    triggered_by: str | None = None
    now = int(time())

    for field_name, field_value in normalized_fields:
        key = _attempt_key(scope, field_name, field_value)
        attempts = cache.get(key, 0) + 1
        cache.set(key, attempts, timeout=window_seconds)

        if attempts >= attempts_limit and triggered_by is None:
            triggered_by = field_name

    if triggered_by is not None:
        blocked_until = now + cooldown_seconds

        for field_name, field_value in normalized_fields:
            cache.set(
                _block_key(scope, field_name, field_value),
                {"blocked_until": blocked_until},
                timeout=cooldown_seconds,
            )
            cache.delete(_attempt_key(scope, field_name, field_value))

        return RateLimitState(
            blocked=True,
            remaining_seconds=cooldown_seconds,
            remaining_minutes=ceil(cooldown_seconds / 60),
            attempts_limit=attempts_limit,
            triggered_by=triggered_by,
        )

    return RateLimitState(
        blocked=False,
        remaining_seconds=0,
        remaining_minutes=0,
        attempts_limit=attempts_limit,
        triggered_by=None,
    )


def reset_rate_limit(
    *,
    scope: str,
    fields: Iterable[RateLimitField],
) -> None:
    """
    Reset attempt counters and active cooldowns for all provided fields.
    Useful after a successful action.
    """
    for field in fields:
        normalized = _normalize_value(field.value)
        if not normalized:
            continue

        cache.delete(_attempt_key(scope, field.name, normalized))
        cache.delete(_block_key(scope, field.name, normalized))