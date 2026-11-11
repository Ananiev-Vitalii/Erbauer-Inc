from functools import partial

from django.db import transaction
from django.db.models import Model
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from account.models import CheatSheet, CheatSheetStep
from account.services.cache import invalidate_cheat_sheet_cache


@receiver(
    pre_save,
    sender=CheatSheetStep,
    dispatch_uid="account.cheat_sheet_cache:previous_parent",
)
def remember_previous_cheat_sheet(
    sender: type[CheatSheetStep],
    instance: CheatSheetStep,
    using: str,
    raw: bool,
    **kwargs: object,
) -> None:
    """Remember the stored parent so moving a step invalidates both guides."""
    previous_id = None
    if instance.pk is not None and not raw:
        previous_id = (
            sender._base_manager.using(using).filter(pk=instance.pk)
            .values_list("cheatsheet_id", flat=True)
            .first()
        )
    instance._previous_cheat_sheet_id = previous_id


@receiver(
    [post_save, post_delete],
    sender=CheatSheet,
    dispatch_uid="account.cheat_sheet_cache:guide_changed",
)
@receiver(
    [post_save, post_delete],
    sender=CheatSheetStep,
    dispatch_uid="account.cheat_sheet_cache:step_changed",
)
def schedule_cheat_sheet_cache_invalidation(
    sender: type[Model],
    instance: CheatSheet | CheatSheetStep,
    using: str,
    **kwargs: object,
) -> None:
    """Capture affected IDs and invalidate only after the database commits."""
    if isinstance(instance, CheatSheetStep):
        previous_id = instance.__dict__.pop("_previous_cheat_sheet_id", None)
        ids = {instance.cheatsheet_id, previous_id}
        invalidate_list = False
    else:
        ids = {instance.pk}
        invalidate_list = True

    cheat_sheet_ids = tuple(sorted(value for value in ids if value is not None))
    transaction.on_commit(
        partial(
            invalidate_cheat_sheet_cache,
            cheat_sheet_ids,
            invalidate_list=invalidate_list,
        ),
        using=using,
    )
