from django.contrib import admin
from django.utils.html import mark_safe
from django.utils.translation import gettext_lazy as _
from modeltranslation.admin import TranslationAdmin, TranslationTabularInline

from user.admin import custom_admin_site
from main.models import (
    CompanyProfile,
    TeamMember,
    Service,
    Project,
    ProjectImage,
)


@admin.register(CompanyProfile, site=custom_admin_site)
class CompanyProfileAdmin(TranslationAdmin):
    list_display = ("name", "is_active")
    fields = (
        "name",
        "primary_phone",
        "secondary_phone",
        "email",
        "address",
        "favicon",
        "logo",
        "years_on_market",
        "completed_objects_count",
        "employees_count",
        "hero_badge",
        "hero_title",
        "hero_description",
        "services_description",
        "about_description",
        "footer_description",
        "working_hours",
        "facebook_url",
        "instagram_url",
        "telegram_url",
        "is_active",
    )


@admin.register(TeamMember, site=custom_admin_site)
class TeamMemberAdmin(TranslationAdmin):
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
class ServiceAdmin(TranslationAdmin):
    list_display = ("title", "icon_preview")
    search_fields = ("title", "description")
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


class ProjectImageInline(admin.TabularInline):
    model = ProjectImage
    extra = 1
    fields = ("image", "image_preview")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.image:
            return mark_safe(
                f'<img src="{obj.image.url}" width="80" height="80" '
                f'style="object-fit:cover;border-radius:8px;" />'
            )
        return "—"

    image_preview.short_description = _("Preview")


@admin.register(Project, site=custom_admin_site)
class ProjectAdmin(TranslationAdmin):
    list_display = (
        "title",
        "category",
        "cover_preview",
        "images_count",
    )
    list_filter = ("category",)
    search_fields = ("title", "short_description")
    fields = (
        "title",
        "category",
        "short_description",
        "cover_image",
        "cover_preview",
    )
    readonly_fields = ("cover_preview",)
    inlines = (ProjectImageInline,)

    def cover_preview(self, obj):
        if obj.cover_image:
            return mark_safe(
                f'<img src="{obj.cover_image.url}" width="80" height="80" '
                f'style="object-fit:cover;border-radius:8px;" />'
            )
        return "—"

    cover_preview.short_description = _("Cover preview")

    def images_count(self, obj):
        return obj.images.count()

    images_count.short_description = _("Gallery images")


@admin.register(ProjectImage, site=custom_admin_site)
class ProjectImageAdmin(admin.ModelAdmin):
    list_display = ("project", "image_preview")
    list_filter = ("project__category",)
    search_fields = ("project__title",)
    fields = (
        "project",
        "image",
        "image_preview",
    )
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.image:
            return mark_safe(
                f'<img src="{obj.image.url}" width="80" height="80" '
                f'style="object-fit:cover;border-radius:8px;" />'
            )
        return "—"

    image_preview.short_description = _("Preview")
