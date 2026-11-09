from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.core.files.storage import FileSystemStorage, Storage
from django.db import transaction
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django_cleanup.signals import cleanup_post_delete

from main.models import ProjectImage, Service
from main.signals import remove_empty_parent_dirs
from main.tests.helpers import create_company, create_project, create_team_member


class HomepageInvalidationSignalTests(TestCase):
    def test_saving_registered_models_defers_invalidation_until_commit(self) -> None:
        member = create_team_member()
        instances = (create_company(), Service.objects.create(title_en="Service"),
                     create_project(), member, member.employee,
                     member.employee.position)
        for instance in instances:
            with self.subTest(model=type(instance).__name__):
                with patch("main.signals.invalidate_homepage_cache") as invalidate:
                    with self.captureOnCommitCallbacks(execute=True):
                        instance.save()
                        invalidate.assert_not_called()
                    invalidate.assert_called_once_with()

    def test_deleting_registered_models_invalidates_after_commit(self) -> None:
        member = create_team_member()
        instances = (member, member.employee, member.employee.position,
                     create_project(), Service.objects.create(title_en="Service"),
                     create_company())
        for instance in instances:
            with self.subTest(model=type(instance).__name__):
                with patch("main.signals.invalidate_homepage_cache") as invalidate:
                    with self.captureOnCommitCallbacks(execute=True):
                        instance.delete()
                        invalidate.assert_not_called()
                    self.assertGreaterEqual(invalidate.call_count, 1)

    def test_rollback_discards_pending_invalidation(self) -> None:
        with patch("main.signals.invalidate_homepage_cache") as invalidate:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                with self.assertRaises(RuntimeError):
                    with transaction.atomic():
                        Service.objects.create(title_en="Rolled back")
                        raise RuntimeError("test rollback")
            invalidate.assert_not_called()
            self.assertEqual(callbacks, [])
        self.assertFalse(Service.objects.filter(title_en="Rolled back").exists())

    def test_repeated_saves_schedule_safe_repeated_callbacks(self) -> None:
        with patch("main.signals.invalidate_homepage_cache") as invalidate:
            with self.captureOnCommitCallbacks(execute=True):
                service = Service.objects.create(title_en="Service")
                service.save()
                invalidate.assert_not_called()
            self.assertEqual(invalidate.call_count, 2)


class HomepageCommitTests(TransactionTestCase):
    def test_autocommit_and_explicit_commit_execute_invalidation(self) -> None:
        with patch("main.signals.invalidate_homepage_cache") as invalidate:
            Service.objects.create(title_en="Autocommit")
            invalidate.assert_called_once_with()
            invalidate.reset_mock()
            with transaction.atomic():
                Service.objects.create(title_en="Atomic commit")
                invalidate.assert_not_called()
            invalidate.assert_called_once_with()


class LocalFileCleanupTests(SimpleTestCase):
    def setUp(self) -> None:
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.media_root = self.root / "media"
        self.media_root.mkdir()
        self.enterContext(override_settings(MEDIA_ROOT=self.media_root))

    def test_receiver_removes_empty_parents_but_keeps_media_root(self) -> None:
        parent = self.media_root / "projects" / "gallery"
        parent.mkdir(parents=True)
        file = ProjectImage(image="projects/gallery/deleted.jpg").image
        cleanup_post_delete.send(sender=ProjectImage, file=file)
        self.assertFalse((self.media_root / "projects").exists())
        self.assertTrue(self.media_root.is_dir())

    def test_nonempty_directory_stops_cleanup(self) -> None:
        parent = self.media_root / "projects" / "gallery"
        parent.mkdir(parents=True)
        (parent / "remaining.txt").write_text("keep", encoding="utf-8")
        file = ProjectImage(image="projects/gallery/deleted.jpg").image
        remove_empty_parent_dirs(ProjectImage, file)
        self.assertTrue((parent / "remaining.txt").is_file())
        self.assertTrue(parent.parent.exists())

    def test_paths_outside_media_root_are_not_removed(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        file = ProjectImage(image="deleted.jpg").image
        file.storage = FileSystemStorage(location=outside)
        remove_empty_parent_dirs(ProjectImage, file)
        self.assertTrue(outside.is_dir())

    def test_absent_file_and_storage_without_local_path_are_skipped(self) -> None:
        remove_empty_parent_dirs(ProjectImage, ProjectImage().image)
        for error in (NotImplementedError(), ValueError()):
            with self.subTest(error=type(error).__name__):
                file = ProjectImage(image="deleted.jpg").image
                file.storage = Mock(spec=Storage)
                file.storage.path.side_effect = error
                remove_empty_parent_dirs(ProjectImage, file)
        self.assertTrue(self.media_root.is_dir())

    def test_unexpected_path_error_is_not_hidden(self) -> None:
        file = ProjectImage(image="deleted.jpg").image
        file.storage = Mock(spec=Storage)
        file.storage.path.side_effect = RuntimeError("test path failure")
        with self.assertRaises(RuntimeError):
            remove_empty_parent_dirs(ProjectImage, file)
