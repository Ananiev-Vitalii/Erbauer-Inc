from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from account.models import Employee


def team_member_directory_path(instance: "TeamMember", filename: str) -> str:
    profile_slug = slugify(f"{instance.employee.last_name}_{instance.employee.email}")
    return f"team_member/{profile_slug}/{filename}"


def company_logo_upload_path(instance: "CompanyProfile", filename: str) -> str:
    return f"company/logo/{filename}"


class CompanyProfile(models.Model):
    name = models.CharField(_("Company name"), max_length=50, unique=True)
    primary_phone = models.CharField(_("Primary phone"), max_length=32)
    secondary_phone = models.CharField(_("Secondary phone"), max_length=32, blank=True)
    email = models.EmailField(_("Email"))
    address = models.CharField(_("Address"), max_length=255)
    working_hours = models.TextField(_("Working hours"))
    logo = models.ImageField(
        _("Company logo"),
        upload_to=company_logo_upload_path,
        blank=True,
    )

    years_on_market = models.PositiveSmallIntegerField(
        _("Years on the market"), default=0
    )
    completed_objects_count = models.PositiveIntegerField(
        _("Completed objects count"), default=0
    )
    employees_count = models.PositiveIntegerField(_("Employees count"), default=0)
    about = models.TextField(_("About"), blank=True)

    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    facebook_url = models.URLField(_("Facebook URL"), blank=True)
    instagram_url = models.URLField(_("Instagram URL"), blank=True)
    telegram_url = models.URLField(_("Telegram URL"), blank=True)

    is_active = models.BooleanField(_("Is active"), default=True)

    class Meta:
        verbose_name = _("Company Profile")
        verbose_name_plural = _("Company Profiles")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name


class TeamMember(models.Model):
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="team_member",
        verbose_name=_("Employee"),
    )
    description = models.TextField(_("Description"), blank=True)
    photo = models.ImageField(
        _("Photo"),
        upload_to=team_member_directory_path,
        default="team_member/default.jpg",
        blank=True,
    )
    display_order = models.PositiveSmallIntegerField(_("Display order"), default=0)
    is_visible = models.BooleanField(_("Is visible"), default=True)

    class Meta:
        verbose_name = _("Team Member")
        verbose_name_plural = _("Team Members")
        ordering = ["display_order", "id"]

    def __str__(self):
        full_name = f"{self.employee.first_name} {self.employee.last_name}".strip()
        return full_name or str(self.display_order)
