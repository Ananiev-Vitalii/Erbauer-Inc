from django.contrib import admin

from user.admin import custom_admin_site
from main.models import CompanyProfile, TeamMember


@admin.register(CompanyProfile, site=custom_admin_site)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    fields = (
        "name",
        "primary_phone",
        "secondary_phone",
        "email",
        "address",
        "logo",
        "years_on_market",
        "completed_objects_count",
        "employees_count",
        "about",
        "footer_description",
        "working_hours",
        "facebook_url",
        "instagram_url",
        "telegram_url",
        "is_active",
    )


@admin.register(TeamMember, site=custom_admin_site)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("employee", "display_order", "is_visible")
    list_filter = ("is_visible",)
    search_fields = ("employee__first_name", "employee__last_name")
    fields = (
        "employee",
        "description",
        "photo",
        "display_order",
        "is_visible",
    )
