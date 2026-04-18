from django.core.cache import cache
from django.conf import settings

from main.models import CompanyProfile, Project, Service, TeamMember

CACHE_TIMEOUT = settings.CACHE_DEFAULT_TIMEOUT


def get_company_base_cached():
    return cache.get_or_set(
        "company_base",
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


def get_homepage_company_profile_cached():
    return cache.get_or_set(
        "homepage:company_profile",
        lambda: CompanyProfile.objects.filter(is_active=True).first(),
        CACHE_TIMEOUT,
    )


def get_homepage_services_cached():
    return cache.get_or_set(
        "homepage:services",
        lambda: list(Service.objects.all()),
        CACHE_TIMEOUT,
    )


def get_homepage_projects_cached():
    return cache.get_or_set(
        "homepage:projects",
        lambda: list(Project.objects.all()[:4]),
        CACHE_TIMEOUT,
    )


def get_homepage_team_members_cached():
    return cache.get_or_set(
        "homepage:team_members",
        lambda: list(
            TeamMember.objects.filter(is_visible=True).select_related(
                "employee", "employee__position"
            )[:8]
        ),
        CACHE_TIMEOUT,
    )
