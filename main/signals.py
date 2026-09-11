from pathlib import Path

from django.conf import settings
from django_cleanup.signals import cleanup_post_delete


def remove_empty_parent_dirs(sender, file, **kwargs):
    media_root = Path(settings.MEDIA_ROOT).resolve()

    try:
        current_dir = Path(file.path).resolve().parent
    except ValueError:
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
