from unittest.mock import patch

from django.test import Client, RequestFactory, SimpleTestCase
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.translation import override
from kombu.exceptions import OperationalError

from core.services.rate_limit import RateLimitState
from core.services.rate_limit_redis import RateLimitUnavailable
from main.tests.helpers import contact_data
from main.views import ContactFormView


class ContactFormViewTests(SimpleTestCase):
    def setUp(self) -> None:
        self.url = reverse("main:contact_submit")
        self.read_state = self.enterContext(
            patch("main.views.get_contact_form_rate_limit_state")
        )
        self.register = self.enterContext(
            patch("main.views.register_contact_form_attempt")
        )
        self.publish = self.enterContext(
            patch("main.views.send_contact_email_task.apply_async")
        )
        self.render = self.enterContext(
            patch("main.views.render_to_string", return_value="")
        )
        self.emergency_render = self.enterContext(
            patch("core.mixins.render_to_string", return_value="")
        )
        allowed = RateLimitState(False, 0, 0, 10)
        self.read_state.return_value = allowed
        self.register.return_value = allowed

    def test_get_is_not_allowed_and_does_not_register_an_attempt(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)
        self.read_state.assert_not_called()
        self.register.assert_not_called()
        self.publish.assert_not_called()

    def test_valid_post_queues_only_validated_data_and_active_language(self) -> None:
        for language in ("en", "uk"):
            with self.subTest(language=language), override(language):
                self.client.cookies["django_language"] = language
                self.publish.reset_mock()
                self.read_state.reset_mock()
                self.register.reset_mock()
                response = self.client.post(self.url, contact_data())
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["Content-Type"],
                                 "text/html; charset=utf-8")
                arguments = self.publish.call_args.kwargs
                self.assertEqual(arguments["kwargs"], {
                    "data": {
                        "name": contact_data()["name"],
                        "phone": "+16045550123",
                        "message": contact_data()["message"],
                    },
                    "language": language,
                })
                self.assertFalse(arguments["retry"])
                for value in arguments["kwargs"]["data"].values():
                    self.assertNotIn(value, arguments["kwargsrepr"])
                self.publish.assert_called_once()
                self.read_state.assert_called_once()
                self.register.assert_called_once()
                context = self.render.call_args.args[1]
                self.assertTrue(context["form"].is_success)
                self.assertFalse(context["form"].is_bound)
                self.assertTrue(context["csrf_token"])
                self.assertNotIn("request", self.render.call_args.kwargs)

    def test_invalid_form_stays_bound_and_does_not_publish(self) -> None:
        data = {**contact_data(), "phone": "invalid number"}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        form = self.render.call_args.args[1]["form"]
        self.assertTrue(form.is_bound)
        self.assertEqual(form["phone"].value(), data["phone"])
        self.assertIn("phone", form.errors)
        self.register.assert_called_once()
        self.publish.assert_not_called()

    def test_existing_or_new_cooldown_prevents_publication(self) -> None:
        blocked = RateLimitState(True, 61, 2, 10, "ip")
        for stage in ("read", "register"):
            with self.subTest(stage=stage):
                self.register.reset_mock()
                allowed = RateLimitState(False, 0, 0, 10)
                self.read_state.return_value = blocked if stage == "read" else allowed
                self.register.return_value = blocked
                response = self.client.post(self.url, contact_data())
                self.assertEqual(response.status_code, 200)
                form = self.render.call_args.args[1]["form"]
                self.assertTrue(form.is_bound)
                self.assertEqual(form["message"].value(), contact_data()["message"])
                self.assertTrue(form.service_message)
                self.assertFalse(form.is_success)
                self.assertEqual(self.register.call_count, stage == "register")
                self.publish.assert_not_called()

    def test_broker_failure_preserves_submitted_form(self) -> None:
        self.publish.side_effect = OperationalError("test broker failure")
        response = self.client.post(self.url, contact_data())
        self.assertEqual(response.status_code, 200)
        form = self.render.call_args.args[1]["form"]
        self.assertTrue(form.is_bound)
        self.assertTrue(form.is_valid())
        self.assertFalse(form.is_success)
        self.assertTrue(form.service_message)
        self.assertNotIn("test broker failure", str(form.service_message))
        self.assertEqual(form["message"].value(), contact_data()["message"])
        self.publish.assert_called_once()

    def test_redis_failure_at_either_stage_returns_bound_form_with_503(self) -> None:
        for boundary in (self.read_state, self.register):
            with self.subTest(boundary=boundary):
                boundary.side_effect = RateLimitUnavailable("test failure")
                response = self.client.post(self.url, contact_data())
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.headers["Content-Type"],
                                 "text/html; charset=utf-8")
                context = self.emergency_render.call_args.args[1]
                self.assertTrue(context["form"].is_bound)
                self.assertTrue(context["form"].service_message)
                self.assertNotIn("test failure", str(context["form"].service_message))
                self.assertEqual(context["form"]["phone"].value(),
                                 contact_data()["phone"])
                self.assertTrue(context["csrf_token"])
                self.render.assert_not_called()
                self.publish.assert_not_called()
                boundary.side_effect = None

    def test_programming_errors_are_not_converted_to_success(self) -> None:
        self.read_state.side_effect = ValueError("test programming error")
        with self.assertRaises(ValueError):
            ContactFormView.as_view()(
                RequestFactory().post(self.url, contact_data())
            )
        self.publish.assert_not_called()

    def test_rendered_csrf_token_can_be_used_for_another_post(self) -> None:
        response = self.client.post(self.url, contact_data())
        token = self.render.call_args.args[1]["csrf_token"]
        protected_client = Client(enforce_csrf_checks=True)
        protected_client.cookies["csrftoken"] = response.cookies["csrftoken"].value
        response = protected_client.post(
            self.url, {**contact_data(), "csrfmiddlewaretoken": token}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.publish.call_count, 2)

    def test_real_partial_rendering_does_not_query_global_context_data(self) -> None:
        with (
            patch("main.views.render_to_string", wraps=render_to_string),
            patch("core.mixins.render_to_string", wraps=render_to_string),
        ):
            response = self.client.post(self.url, contact_data())
            self.assertEqual(response.status_code, 200)
            self.read_state.side_effect = RateLimitUnavailable("test failure")
            response = self.client.post(self.url, contact_data())
            self.assertEqual(response.status_code, 503)
        self.publish.assert_called_once()
