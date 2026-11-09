from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from main.forms import ContactForm
from main.models import ProjectCategory, ProjectImage, Service
from main.tests.helpers import (
    create_company, create_project, create_team_member, isolated_cache_settings,
)


class PublicViewTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.company = create_company()
        cls.services = [Service.objects.create(
            title_en=f"Service {number:02}", description_en="Description"
        ) for number in range(13)]
        cls.projects = [create_project(number, (
            ProjectCategory.RESIDENTIAL if number < 5 else ProjectCategory.COMMERCIAL
        )) for number in range(8)]
        cls.members = [create_team_member(number, number + 1)
                       for number in range(5)]
        cls.image = ProjectImage.objects.create(
            project=cls.projects[0], image="projects/gallery/test.jpg"
        )

    def setUp(self) -> None:
        self.enterContext(override_settings(CACHES=isolated_cache_settings()))

    def test_home_context_uses_cached_data_and_splits_service_pages(self) -> None:
        with patch("main.views.get_homepage_services_cached",
                   return_value=self.services) as services:
            response = self.client.get(reverse("main:home"))
        self.assertEqual(response.status_code, 200)
        services.assert_called_once_with()
        self.assertEqual(response.context["company_profile"].pk, self.company.pk)
        self.assertEqual([len(page) for page in response.context["service_pages"]],
                         [6, 6, 1])
        self.assertEqual(response.context["service_pages"][0], self.services[:6])
        self.assertEqual([item.pk for item in response.context["projects"]],
                         [item.pk for item in reversed(self.projects[-4:])])
        self.assertTrue(response.context["has_more_team_members"])
        self.assertIsInstance(response.context["form"], ContactForm)
        self.assertFalse(response.context["form"].is_bound)

    def test_home_handles_empty_data(self) -> None:
        with (
            patch("main.views.get_homepage_company_profile_cached", return_value=None),
            patch("main.views.get_homepage_services_cached", return_value=[]),
            patch("main.views.get_homepage_projects_cached", return_value=[]),
            patch("main.views.get_homepage_team_members_cached", return_value=[]),
        ):
            response = self.client.get(reverse("main:home"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["company_profile"])
        self.assertEqual(response.context["service_pages"], [])
        self.assertFalse(response.context["has_more_team_members"])

    def test_project_list_is_ordered_and_paginated(self) -> None:
        response = self.client.get(reverse("main:project_list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_category"], "all")
        self.assertEqual(response.context["paginator"].count, 8)
        self.assertEqual([item.pk for item in response.context["projects"]],
                         [item.pk for item in reversed(self.projects[2:])])
        response = self.client.get(reverse("main:project_list"), {"page": 2})
        self.assertEqual([item.pk for item in response.context["projects"]],
                         [self.projects[1].pk, self.projects[0].pk])

    def test_more_team_members_flag_has_a_four_member_boundary(self) -> None:
        for count in (4, 5):
            with self.subTest(count=count):
                with patch("main.views.get_homepage_team_members_cached",
                           return_value=self.members[:count]):
                    response = self.client.get(reverse("main:home"))
                self.assertEqual(response.context["has_more_team_members"], count > 4)

    def test_categories_filter_and_unknown_categories_fall_back_to_all(self) -> None:
        for category, count in (("residential", 5), ("commercial", 3),
                                ("unknown", 8)):
            with self.subTest(category=category):
                response = self.client.get(reverse("main:project_list"),
                                           {"category": category})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["paginator"].count, count)
                expected = category if category != "unknown" else "all"
                self.assertEqual(response.context["current_category"], expected)
                if category != "unknown":
                    self.assertTrue(all(project.category == category
                                        for project in response.context["projects"]))

    def test_invalid_pages_and_missing_project_return_404(self) -> None:
        for page in ("invalid", "0", "999"):
            with self.subTest(page=page):
                response = self.client.get(reverse("main:project_list"), {"page": page})
                self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("main:project_detail", args=[999999]))
        self.assertEqual(response.status_code, 404)

    def test_detail_contains_the_project_and_prefetched_images(self) -> None:
        response = self.client.get(
            reverse("main:project_detail", args=[self.projects[0].pk])
        )
        self.assertEqual(response.status_code, 200)
        project = response.context["project"]
        self.assertEqual(project.pk, self.projects[0].pk)
        with self.assertNumQueries(0):
            self.assertEqual([image.pk for image in project.images.all()],
                             [self.image.pk])

    def test_privacy_policy_context_contains_the_approved_revision_date(self) -> None:
        response = self.client.get(reverse("main:privacy_policy"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["privacy_policy_updated_on"],
                         date(2026, 11, 7))
