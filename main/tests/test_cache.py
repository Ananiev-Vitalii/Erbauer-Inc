from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils.translation import override
from redis.exceptions import ConnectionError as RedisConnectionError

from main.models import Service
from main.services import cache as homepage_cache
from main.tests.helpers import (
    create_company, create_project, create_team_member, isolated_cache_settings,
)


class HomepageCacheTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.company = create_company()
        create_company("Inactive company", active=False)
        cls.service = Service.objects.create(
            title_en="Service", title_uk="Service UK",
            description_en="Description EN", description_uk="Description UK",
        )
        cls.projects = [create_project(number) for number in range(5)]
        cls.later_member = create_team_member(1, 9)
        cls.first_member = create_team_member(2, 2)
        create_team_member(3, 10, visible=False)

    def setUp(self) -> None:
        self.enterContext(override_settings(CACHES=isolated_cache_settings()))
        self.enterContext(override("en"))

    def test_all_data_functions_query_on_miss_and_reuse_cached_results(self) -> None:
        cases = (
            (homepage_cache.get_company_base_cached, "company_base"),
            (homepage_cache.get_homepage_company_profile_cached,
             "homepage:company_profile"),
            (homepage_cache.get_homepage_services_cached, "homepage:services"),
            (homepage_cache.get_homepage_projects_cached, "homepage:projects"),
            (homepage_cache.get_homepage_team_members_cached, "homepage:team_members"),
        )
        for function, prefix in cases:
            with self.subTest(prefix=prefix):
                with self.assertNumQueries(1):
                    first = function()
                with self.assertNumQueries(0):
                    second = function()
                self.assertEqual(first, second)
                self.assertIsNotNone(cache.get(f"{prefix}:en"))

    def test_results_follow_filters_ordering_and_project_limit(self) -> None:
        self.assertEqual(homepage_cache.get_homepage_company_profile_cached().pk,
                         self.company.pk)
        self.assertEqual(homepage_cache.get_company_base_cached().name,
                         self.company.name)
        projects = homepage_cache.get_homepage_projects_cached()
        self.assertEqual([item.pk for item in projects],
                         [item.pk for item in reversed(self.projects[-4:])])
        members = homepage_cache.get_homepage_team_members_cached()
        self.assertEqual([item.pk for item in members],
                         [self.first_member.pk, self.later_member.pk])
        with self.assertNumQueries(0):
            self.assertTrue(all(member.employee.first_name and
                                member.employee.position.name for member in members))

    def test_language_keys_are_separate_and_data_remains_language_aware(self) -> None:
        for language, expected in (("en", "Description EN"),
                                   ("uk", "Description UK")):
            with self.subTest(language=language), override(language):
                with self.assertNumQueries(1):
                    result = homepage_cache.get_homepage_services_cached()
                self.assertEqual(result[0].description, expected)
                self.assertIsNotNone(cache.get(f"homepage:services:{language}"))
                with self.assertNumQueries(0):
                    homepage_cache.get_homepage_services_cached()

    def test_configured_ttl_is_passed_to_all_data_caches(self) -> None:
        functions = (
            homepage_cache.get_company_base_cached,
            homepage_cache.get_homepage_company_profile_cached,
            homepage_cache.get_homepage_services_cached,
            homepage_cache.get_homepage_projects_cached,
            homepage_cache.get_homepage_team_members_cached,
        )
        with patch.object(homepage_cache, "CACHE_TIMEOUT", 30):
            for function in functions:
                with self.subTest(function=function.__name__):
                    with patch.object(homepage_cache.cache, "get_or_set") as get:
                        function()
                    self.assertEqual(get.call_args.args[2], 30)

    def test_expiration_causes_a_new_database_read_without_sleeping(self) -> None:
        with patch.object(homepage_cache, "CACHE_TIMEOUT", 30):
            with patch("django.core.cache.backends.locmem.time.time",
                       return_value=1000):
                homepage_cache.get_homepage_services_cached()
            with patch("django.core.cache.backends.locmem.time.time",
                       return_value=1029):
                with self.assertNumQueries(0):
                    homepage_cache.get_homepage_services_cached()
            with patch("django.core.cache.backends.locmem.time.time",
                       return_value=1031):
                with self.assertNumQueries(1):
                    homepage_cache.get_homepage_services_cached()

    def test_no_active_company_returns_none(self) -> None:
        self.company.is_active = False
        self.company.save(update_fields=["is_active"])
        self.assertIsNone(homepage_cache.get_company_base_cached())
        self.assertIsNone(homepage_cache.get_homepage_company_profile_cached())

    def test_invalidation_deletes_only_the_five_language_keys(self) -> None:
        with override_settings(LANGUAGES=[("en", "English"), ("uk", "Ukrainian")]):
            keys = [f"{prefix}:{language}" for language, _ in settings.LANGUAGES
                    for prefix in ("company_base", "homepage:company_profile",
                                   "homepage:services", "homepage:projects",
                                   "homepage:team_members")]
            unrelated = "rate_limit:v2:unrelated:attempt:ip:192.0.2.1"
            cache.set_many({key: "cached" for key in [*keys, unrelated]})
            homepage_cache.invalidate_homepage_cache()
            self.assertTrue(all(cache.get(key) is None for key in keys))
            self.assertEqual(cache.get(unrelated), "cached")

    def test_invalidation_logs_provider_failure_without_sensitive_details(self) -> None:
        with patch.object(homepage_cache.cache, "delete_many") as delete:
            delete.side_effect = RedisConnectionError("test-sensitive-marker")
            with self.assertLogs("main.services.cache", level="ERROR") as logs:
                homepage_cache.invalidate_homepage_cache()
        self.assertNotIn("test-sensitive-marker", " ".join(logs.output))

    def test_invalidation_does_not_hide_programming_errors(self) -> None:
        with patch.object(homepage_cache.cache, "delete_many", side_effect=TypeError):
            with self.assertRaises(TypeError):
                homepage_cache.invalidate_homepage_cache()

    def test_missing_active_language_uses_the_default_language_key(self) -> None:
        with override(None):
            homepage_cache.get_homepage_services_cached()
        self.assertIsNotNone(cache.get(f"homepage:services:{settings.LANGUAGE_CODE}"))

    def test_committed_save_invalidates_data_before_the_next_read(self) -> None:
        homepage_cache.get_homepage_services_cached()
        with self.captureOnCommitCallbacks(execute=True):
            self.service.description_en = "Updated description"
            self.service.save(update_fields=["description_en"])
            cached = homepage_cache.get_homepage_services_cached()
            self.assertEqual(cached[0].description, "Description EN")
        with self.assertNumQueries(1):
            refreshed = homepage_cache.get_homepage_services_cached()
        self.assertEqual(refreshed[0].description, "Updated description")
