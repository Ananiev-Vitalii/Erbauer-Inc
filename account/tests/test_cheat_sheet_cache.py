from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils.translation import override

from account.models import CheatSheet, CheatSheetStep
from account.services.cache import get_cheat_sheet_steps_cached, get_cheat_sheets_cached
from main.tests.helpers import isolated_cache_settings


class CheatSheetCacheTests(TestCase):
    def setUp(self) -> None:
        self.enterContext(override_settings(CACHES=isolated_cache_settings()))
        self.guide = CheatSheet.objects.create(name_en="Guide", name_uk="Guide")
        self.step = CheatSheetStep.objects.create(
            cheatsheet=self.guide, step_number=1, image="cheatsheets/old.png",
            description_en="Old description", description_uk="Old description",
        )

    def warm(self) -> None:
        for language, _ in settings.LANGUAGES:
            with override(language):
                get_cheat_sheets_cached()
                get_cheat_sheet_steps_cached(self.guide.pk)

    def test_edits_refresh_both_language_caches_only_after_commit(self) -> None:
        self.warm()
        with self.captureOnCommitCallbacks(execute=True):
            self.guide.name_en = self.guide.name_uk = "Updated guide"
            self.guide.save()
            self.step.description_en = self.step.description_uk = "Updated description"
            self.step.image = "cheatsheets/new.png"
            self.step.save()
            for language, _ in settings.LANGUAGES:
                with override(language):
                    self.assertEqual(get_cheat_sheets_cached()[0].name, "Guide")
                    self.assertEqual(
                        get_cheat_sheet_steps_cached(self.guide.pk)[0].image.name,
                        "cheatsheets/old.png",
                    )
        for language, _ in settings.LANGUAGES:
            with override(language):
                self.assertEqual(get_cheat_sheets_cached()[0].name, "Updated guide")
                steps = get_cheat_sheet_steps_cached(self.guide.pk)
                self.assertEqual(steps[0].description, "Updated description")
                self.assertEqual(steps[0].image.name, "cheatsheets/new.png")

    def test_moving_step_invalidates_old_and_new_guides_without_clearing_others(
        self,
    ) -> None:
        destination = CheatSheet.objects.create(name_en="Destination")
        untouched = CheatSheet.objects.create(name_en="Untouched")
        self.warm()
        for language, _ in settings.LANGUAGES:
            cache.set(f"account:cheat_sheet:steps:{destination.pk}:{language}", [])
            cache.set(
                f"account:cheat_sheet:steps:{untouched.pk}:{language}", "sentinel"
            )
        with self.captureOnCommitCallbacks(execute=True):
            self.step.cheatsheet = destination
            self.step.save(update_fields=["cheatsheet"])
        for language, _ in settings.LANGUAGES:
            with override(language):
                self.assertEqual(get_cheat_sheet_steps_cached(self.guide.pk), [])
                steps = get_cheat_sheet_steps_cached(destination.pk)
                self.assertEqual([step.pk for step in steps], [self.step.pk])
                self.assertEqual(
                    cache.get(f"account:cheat_sheet:steps:{untouched.pk}:{language}"),
                    "sentinel",
                )

    def test_rollback_keeps_existing_cached_data(self) -> None:
        self.warm()
        with patch("account.signals.invalidate_cheat_sheet_cache") as invalidate:
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(RuntimeError), transaction.atomic():
                    self.step.description_en = "Rolled back"
                    self.step.save()
                    raise RuntimeError("Abort edit")
            invalidate.assert_not_called()
        self.step.refresh_from_db()
        self.assertEqual(self.step.description_en, "Old description")
        with override("en"):
            self.assertEqual(
                get_cheat_sheet_steps_cached(self.guide.pk)[0].description,
                "Old description",
            )

    def test_queryset_deletion_invalidates_parent_and_cascaded_steps(self) -> None:
        self.warm()
        guide_id = self.guide.pk
        with self.captureOnCommitCallbacks(execute=True):
            CheatSheet.objects.filter(pk=guide_id).delete()
        for language, _ in settings.LANGUAGES:
            with override(language):
                self.assertEqual(get_cheat_sheets_cached(), [])
                self.assertEqual(get_cheat_sheet_steps_cached(guide_id), [])
