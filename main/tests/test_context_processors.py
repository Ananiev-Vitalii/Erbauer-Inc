from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase

from main.context_processors import company_base


class CompanyContextProcessorTests(SimpleTestCase):
    def test_anonymous_context_does_not_query_profiles(self) -> None:
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(is_authenticated=False)
        with (
            patch("main.context_processors.get_company_base_cached",
                  return_value=None),
            patch("main.context_processors.Profile.objects.filter") as profiles,
        ):
            self.assertEqual(company_base(request), {"company_base": None,
                                                     "profile": None})
        profiles.assert_not_called()

    def test_authenticated_context_contains_the_users_profile(self) -> None:
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(is_authenticated=True)
        company = Mock()
        profile = Mock()
        with (
            patch("main.context_processors.get_company_base_cached",
                  return_value=company),
            patch("main.context_processors.Profile.objects.filter") as profiles,
        ):
            profiles.return_value.first.return_value = profile
            context = company_base(request)
        profiles.assert_called_once_with(employee__user=request.user)
        self.assertEqual(context, {"company_base": company, "profile": profile})
