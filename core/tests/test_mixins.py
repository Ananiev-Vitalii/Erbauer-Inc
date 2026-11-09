from unittest.mock import patch

from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, SimpleTestCase
from django.views import View

from core.mixins import RateLimitUnavailableMixin
from core.services.rate_limit_redis import RateLimitUnavailable


class FailingProtectedView(RateLimitUnavailableMixin, View):
    failure = RateLimitUnavailable("test provider failure")

    def get(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        raise self.failure


class RateLimitUnavailableMixinTests(SimpleTestCase):
    def test_non_partial_failure_returns_503_without_request_context(self) -> None:
        with patch("core.mixins.render_to_string", return_value="") as render:
            response = FailingProtectedView.as_view()(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(render.call_args.args[0], "core/errors/503.html")
        self.assertTrue(render.call_args.args[1]["message"])
        self.assertNotIn("request", render.call_args.kwargs)

    def test_programming_errors_escape_the_mixin(self) -> None:
        with self.assertRaises(ValueError):
            FailingProtectedView.as_view(failure=ValueError("test error"))(
                RequestFactory().get("/")
            )
