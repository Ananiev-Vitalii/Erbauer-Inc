from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from time import time
from typing import Iterable

from core.services.rate_limit_redis import execute_rate_limit


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
    return f"rate_limit:v2:{scope}:attempt:{field_name}:{field_value}"


def _block_key(scope: str, field_name: str, field_value: str) -> str:
    return f"rate_limit:v2:{scope}:block:{field_name}:{field_value}"


def _execute(
    *,
    scope: str,
    fields: Iterable[RateLimitField],
    operation: str,
    attempts_limit: int,
    window_seconds: int = 0,
    cooldown_seconds: int = 0,
) -> RateLimitState:
    normalized_fields = []
    keys = []
    for field in fields:
        value = _normalize_value(field.value)
        if not value:
            continue
        normalized_fields.append(field.name)
        keys.extend(
            (
                _attempt_key(scope, field.name, value),
                _block_key(scope, field.name, value),
            )
        )

    remaining, matched = (0, 0)
    if keys:
        remaining, matched = execute_rate_limit(
            keys=keys,
            operation=operation,
            now=int(time()),
            attempts_limit=attempts_limit,
            window_seconds=window_seconds,
            cooldown_seconds=cooldown_seconds,
        )

    return RateLimitState(
        blocked=matched > 0,
        remaining_seconds=remaining,
        remaining_minutes=ceil(remaining / 60) if remaining > 0 else 0,
        attempts_limit=attempts_limit,
        triggered_by=normalized_fields[matched - 1] if matched else None,
    )


def get_rate_limit_state(
    *,
    scope: str,
    fields: Iterable[RateLimitField],
    attempts_limit: int,
) -> RateLimitState:
    return _execute(
        scope=scope,
        fields=fields,
        operation="read",
        attempts_limit=attempts_limit,
    )


def register_rate_limit_attempt(
    *,
    scope: str,
    fields: Iterable[RateLimitField],
    attempts_limit: int,
    window_seconds: int,
    cooldown_seconds: int,
) -> RateLimitState:
    """Register attempts atomically; each attempt renews the inactivity window."""
    return _execute(
        scope=scope,
        fields=fields,
        operation="register",
        attempts_limit=attempts_limit,
        window_seconds=window_seconds,
        cooldown_seconds=cooldown_seconds,
    )


def reset_rate_limit(
    *,
    scope: str,
    fields: Iterable[RateLimitField],
) -> None:
    _execute(scope=scope, fields=fields, operation="reset", attempts_limit=0)
