from pathlib import Path
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Model
from django.db.models.fields.files import FieldFile
from django.db.models.signals import post_delete, post_save
from django_cleanup.signals import cleanup_post_delete

from main.services.cache import invalidate_homepage_cache


def schedule_homepage_cache_invalidation(
    sender: type[Model], instance: Model, using: str, **kwargs: Any
) -> None:
    transaction.on_commit(invalidate_homepage_cache, using=using)


for model_label in (
    "main.CompanyProfile",
    "main.Service",
    "main.Project",
    "main.TeamMember",
    "account.Employee",
    "account.Position",
):
    post_save.connect(
        schedule_homepage_cache_invalidation,
        sender=model_label,
        dispatch_uid=f"main.invalidate_homepage_cache:{model_label}:save",
    )
    post_delete.connect(
        schedule_homepage_cache_invalidation,
        sender=model_label,
        dispatch_uid=f"main.invalidate_homepage_cache:{model_label}:delete",
    )


def remove_empty_parent_dirs(
    sender: type[Model], file: FieldFile, **kwargs
) -> None:
    media_root = Path(settings.MEDIA_ROOT).resolve()

    try:
        current_dir = Path(file.path).resolve().parent
    except (ValueError, NotImplementedError):
        return

    while current_dir != media_root and media_root in current_dir.parents:
        try:
            current_dir.rmdir()
        except OSError:
            break

        current_dir = current_dir.parent


cleanup_post_delete.connect(
    remove_empty_parent_dirs,
    dispatch_uid="main.remove_empty_parent_dirs",
)
