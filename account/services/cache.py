from django.conf import settings
from django.core.cache import cache
from django.utils.translation import get_language

from account.models import CheatSheet, CheatSheetStep

CACHE_TIMEOUT = settings.CACHE_DEFAULT_TIMEOUT


def _lang() -> str:
    return get_language() or settings.LANGUAGE_CODE


def get_cheat_sheets_cached():
    language = _lang()
    cache_key = f"account:cheat_sheets:list:{language}"

    return cache.get_or_set(
        cache_key,
        lambda: list(
            CheatSheet.objects.order_by("name")
        ),
        CACHE_TIMEOUT,
    )


def get_cheat_sheet_steps_cached(cheat_sheet_id: int):
    language = _lang()
    cache_key = f"account:cheat_sheet:steps:{cheat_sheet_id}:{language}"

    return cache.get_or_set(
        cache_key,
        lambda: list(
            CheatSheetStep.objects.filter(
                cheatsheet_id=cheat_sheet_id,
            ).order_by("step_number")
        ),
        CACHE_TIMEOUT,
    )