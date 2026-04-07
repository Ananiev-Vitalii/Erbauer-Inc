from django.contrib import admin
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _

from user.admin import custom_admin_site
from main.models import CompanyProfile, TeamMember, Service


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
        "hero_badge",
        "hero_title",
        "hero_description",
        "services_description",
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


@admin.register(Service, site=custom_admin_site)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "icon_preview")

    fields = (
        "title",
        "description",
        "icon",
    )

    def icon_preview(self, obj):
        if obj.icon:
            return mark_safe(
                f'<img src="{obj.icon.url}" width="40" height="40" style="object-fit:cover;border-radius:6px;" />'
            )
        return "—"

    icon_preview.short_description = _("Icon")
