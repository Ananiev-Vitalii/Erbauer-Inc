from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def profile_directory_path(instance: "Profile", filename: str) -> str:
    profile_slug = slugify(f"{instance.employee.last_name}_{instance.employee.email}")
    return f"profiles/{profile_slug}/{filename}"


class Position(models.Model):
    name = models.CharField(_("Job title"), max_length=50, unique=True)

    class Meta:
        verbose_name = _("Job title")
        verbose_name_plural = _("Job titles")

    def __str__(self) -> str:
        return self.name


class Employee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee",
        null=True,
        blank=True,
    )
    first_name = models.CharField(_("First name"), max_length=50)
    last_name = models.CharField(_("Last name"), max_length=50)
    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name=_("Job title"),
    )
    email = models.EmailField(_("Email"), unique=True)
    is_active = models.BooleanField(_("Currently employed"), default=True)

    class Meta:
        verbose_name = _("Employee")
        verbose_name_plural = _("Employees")

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Profile(models.Model):
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("Employee"),
    )
    avatar = models.ImageField(
        _("Avatar"),
        upload_to=profile_directory_path,
        default="profiles/default.png",
        blank=True,
    )
    phone = models.CharField(_("Phone"), max_length=30, blank=True)

    class Meta:
        verbose_name = _("Profile")
        verbose_name_plural = _("Profiles")

    def __str__(self) -> str:
        return f"Profile: {self.employee}"
