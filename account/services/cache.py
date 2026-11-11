from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import get_language
from redis.exceptions import RedisError

from account.models import CheatSheet, CheatSheetStep

CACHE_TIMEOUT = settings.CACHE_DEFAULT_TIMEOUT
logger = logging.getLogger(__name__)


def invalidate_cheat_sheet_cache(
    cheat_sheet_ids: tuple[int, ...],
    *,
    invalidate_list: bool,
) -> None:
    """Delete only affected data keys after a committed model change."""
    keys = [
        f"account:cheat_sheet:steps:{cheat_sheet_id}:{language}"
        for language, _ in settings.LANGUAGES
        for cheat_sheet_id in cheat_sheet_ids
    ]
    if invalidate_list:
        keys.extend(
            f"account:cheat_sheets:list:{language}"
            for language, _ in settings.LANGUAGES
        )
    if not keys:
        return
    try:
        cache.delete_many(keys)
    except RedisError as error:
        logger.error(
            "Cheat sheet cache invalidation failed (%s). "
            "Stale content may remain until cache expiry.",
            type(error).__name__,
        )


def _lang() -> str:
    return get_language() or settings.LANGUAGE_CODE


def get_cheat_sheets_cached() -> list[CheatSheet]:
    language = _lang()
    cache_key = f"account:cheat_sheets:list:{language}"

    return cache.get_or_set(
        cache_key,
        lambda: list(CheatSheet.objects.order_by("name")),
        CACHE_TIMEOUT,
    )


def get_cheat_sheet_steps_cached(cheat_sheet_id: int) -> list[CheatSheetStep]:
    language = _lang()
    cache_key = f"account:cheat_sheet:steps:{cheat_sheet_id}:{language}"

    return cache.get_or_set(
        cache_key,
        lambda: list(
            CheatSheetStep.objects.filter(cheatsheet_id=cheat_sheet_id)
            .order_by("step_number")
        ),
        CACHE_TIMEOUT,
    )
