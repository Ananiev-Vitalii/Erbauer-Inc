from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from account.models import Employee


def team_member_directory_path(instance: "TeamMember", filename: str) -> str:
    profile_slug = slugify(f"{instance.employee.last_name}_{instance.employee.email}")
    return f"team_member/{profile_slug}/{filename}"


class TeamMember(models.Model):
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="team_members",
    )
    description = models.TextField(blank=True)
    photo = models.ImageField(
        upload_to=team_member_directory_path,
        default="team_member/default.jpg",
        blank=True,
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    is_visible = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Team Member")
        verbose_name_plural = _("Team Members")
        ordering = ["display_order", "id"]

    def __str__(self):
        full_name = f"{self.employee.first_name} {self.employee.last_name}".strip()
        return full_name or str(self.display_order)
