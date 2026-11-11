from uuid import uuid4

from account.models import Employee, Position
from main.models import CompanyProfile, Project, ProjectCategory, TeamMember


def isolated_cache_settings() -> dict[str, dict[str, str]]:
    return {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": f"main-tests-{uuid4().hex}",
        }
    }


def create_company(name: str = "Test company", active: bool = True) -> CompanyProfile:
    return CompanyProfile.objects.create(
        name=name,
        is_active=active,
        primary_phone="+16045550123",
        email="company@example.invalid",
        address="1 Test Street",
        city="Vancouver",
        province="BC",
        postal_code="V1A 1A1",
        working_hours_en="Weekdays",
        working_hours_uk="Weekdays",
        about_description_en="About",
        hero_badge="Company",
        hero_title_en="Construction",
        hero_description_en="Description",
        services_description_en="Services",
        footer_description_en="Company information",
        footer_description_uk="Company information",
    )


def create_project(
    number: int = 1, category: str = ProjectCategory.RESIDENTIAL
) -> Project:
    return Project.objects.create(
        title=f"Project {number:03}",
        category=category,
        short_description_en="Project description",
        cover_image=f"projects/test-{number}/cover.jpg",
    )


def create_team_member(
    number: int = 1, order: int = 1, visible: bool = True
) -> TeamMember:
    position = Position.objects.create(
        name_en=f"Position {number}", name_uk=f"Position {number}"
    )
    employee = Employee.objects.create(
        first_name_en=f"First {number}",
        first_name_uk=f"First {number}",
        last_name_en=f"Last {number}",
        last_name_uk=f"Last {number}",
        email=f"employee-{number}@example.invalid",
        position=position,
    )
    return TeamMember.objects.create(
        employee=employee,
        description_en="Team member",
        display_order=order,
        is_visible=visible,
    )


def contact_data() -> dict[str, str]:
    return {
        "name": "Test visitor",
        "phone": "(604) 555-0123",
        "message": "Please contact me about a project.",
        "privacy_policy": "on",
    }
