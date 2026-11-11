from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.db import OperationalError
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.utils.translation import override
from redis.exceptions import ConnectionError as RedisConnectionError

from core.errors.views import custom_server_error


class ServerErrorViewTests(SimpleTestCase):
    def test_server_error_renders_without_infrastructure_context(self) -> None:
        for language in ("en", "uk"):
            for authenticated in (False, True):
                with self.subTest(language=language, authenticated=authenticated):
                    request = RequestFactory().get("/failed-request/")
                    request.user = (
                        Mock(is_authenticated=True)
                        if authenticated
                        else AnonymousUser()
                    )
                    with (
                        override(language),
                        patch(
                            "main.context_processors.get_company_base_cached",
                            side_effect=RedisConnectionError("Redis unavailable"),
                        ) as company,
                        patch(
                            "main.context_processors.Profile.objects.filter",
                            side_effect=OperationalError("Database unavailable"),
                        ) as profile,
                        patch(
                            "core.errors.views.render_to_string",
                            wraps=render_to_string,
                        ) as render,
                    ):
                        response = custom_server_error(request)

                    self.assertEqual(response.status_code, 500)
                    self.assertEqual(
                        response.headers["Content-Type"], "text/html; charset=utf-8"
                    )
                    company.assert_not_called()
                    profile.assert_not_called()
                    render.assert_called_once_with(
                        "core/errors/500.html", {"language": language}
                    )
