import logging

from django.conf import settings
from django.core.cache import cache
from django.utils.translation import get_language
from redis.exceptions import RedisError

from main.models import CompanyProfile, Project, Service, TeamMember

CACHE_TIMEOUT = settings.CACHE_DEFAULT_TIMEOUT
logger = logging.getLogger(__name__)


def invalidate_homepage_cache() -> None:
    """Invalidate public data caches without failing an already committed write."""
    keys = [
        f"{prefix}:{language}"
        for language, _ in settings.LANGUAGES
        for prefix in (
            "company_base",
            "homepage:company_profile",
            "homepage:services",
            "homepage:projects",
            "homepage:team_members",
        )
    ]
    try:
        cache.delete_many(keys)
    except RedisError as error:
        # Provider errors may contain credentials; log only their class name.
        logger.error(
            "Homepage cache invalidation failed (%s). "
            "Stale content may remain until cache expiry.",
            type(error).__name__,
        )


def _lang() -> str:
    return get_language() or settings.LANGUAGE_CODE


def get_company_base_cached() -> CompanyProfile | None:
    language = _lang()
    cache_key = f"company_base:{language}"

    return cache.get_or_set(
        cache_key,
        lambda: CompanyProfile.objects.filter(is_active=True)
        .only(
            "name",
            "favicon",
            "logo",
            "email",
            "footer_description",
            "facebook_url",
            "instagram_url",
            "telegram_url",
        )
        .first(),
        CACHE_TIMEOUT,
    )


def get_homepage_company_profile_cached() -> CompanyProfile | None:
    language = _lang()
    cache_key = f"homepage:company_profile:{language}"

    return cache.get_or_set(
        cache_key,
        lambda: CompanyProfile.objects.filter(is_active=True).first(),
        CACHE_TIMEOUT,
    )


def get_homepage_services_cached() -> list[Service]:
    language = _lang()
    cache_key = f"homepage:services:{language}"

    return cache.get_or_set(
        cache_key,
        lambda: list(Service.objects.all()),
        CACHE_TIMEOUT,
    )


def get_homepage_projects_cached() -> list[Project]:
    language = _lang()
    cache_key = f"homepage:projects:{language}"

    return cache.get_or_set(
        cache_key,
        lambda: list(Project.objects.all()[:4]),
        CACHE_TIMEOUT,
    )


def get_homepage_team_members_cached() -> list[TeamMember]:
    language = _lang()
    cache_key = f"homepage:team_members:{language}"

    return cache.get_or_set(
        cache_key,
        lambda: list(
            TeamMember.objects.filter(is_visible=True).select_related(
                "employee",
                "employee__position",
            )
        ),
        CACHE_TIMEOUT,
    )
