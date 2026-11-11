from contextlib import ExitStack
from unittest.mock import Mock, patch

from anymail.exceptions import AnymailAPIError, AnymailRecipientsRefused
from requests.exceptions import Timeout
from django.contrib.messages import get_messages
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.services.email import EmailDeliveryError
from core.services.rate_limit_redis import RateLimitUnavailable
from main.models import CompanyProfile
from user.models import User
from user.services.email import get_email_company_name, send_verification_email
from user.tests.helpers import employee, state
from user.views import ConfirmUser, CustomPasswordResetView


class EmailWorkflowTests(TestCase):
    def test_shared_gate_accounts_for_each_captcha_outcome_once(self) -> None:
        for view in (ConfirmUser, CustomPasswordResetView):
            for valid in (False, True):
                with self.subTest(view=view.__name__,
                                  valid=valid), ExitStack() as stack:
                    read = stack.enter_context(patch.object(
                        view, "get_email_rate_limit_state", return_value=state()))
                    captcha = stack.enter_context(patch.object(
                        view, "register_captcha_failure", return_value=state()))
                    attempt = stack.enter_context(patch.object(
                        view, "register_email_attempt", return_value=state()))
                    stack.enter_context(patch("user.mixins.verify_turnstile_token",
                                              return_value={"success": valid}))
                    business = stack.enter_context(patch.object(
                        view, "form_valid", return_value=HttpResponse()))
                    response = view.as_view()(self.request())
                    if hasattr(response, "render") and not valid:
                        response.render()
                    self.assertEqual(read.call_count, 2)
                    self.assertEqual(captcha.call_count, int(not valid))
                    self.assertEqual(attempt.call_count, int(valid))
                    self.assertEqual(business.call_count, int(valid))

    def request(self) -> HttpRequest:
        request = RequestFactory().post("/", {"email": "unknown@example.invalid"})
        request.user = Mock(is_authenticated=False)
        request._dont_enforce_csrf_checks = True
        return request

    def test_blocked_and_unavailable_requests_do_not_call_turnstile(self) -> None:
        for view in (ConfirmUser, CustomPasswordResetView):
            for unavailable in (False, True):
                with self.subTest(view=view.__name__, unavailable=unavailable), \
                     patch.object(view, "get_email_rate_limit_state",
                                  side_effect=(
                                      RateLimitUnavailable() if unavailable else None
                                  ),
                                  return_value=state(True)), \
                     patch("user.mixins.verify_turnstile_token") as cloud, \
                     patch.object(view, "register_email_attempt") as attempt, \
                     patch.object(view, "register_captcha_failure") as captcha:
                    response = view.as_view()(self.request())
                    self.assertEqual(response.status_code, 503 if unavailable else 200)
                    cloud.assert_not_called()
                    attempt.assert_not_called()
                    captcha.assert_not_called()

    def test_resend_neutral_result_for_pending_disabled_and_missing_users(self) -> None:
        for verified in (False, True):
            user = User.objects.create_user(
                email=f"pending-{verified}@example.invalid", is_active=False,
                is_verified=verified,
            )
            with patch.object(ConfirmUser, "is_turnstile_valid", return_value=True), \
                 patch.object(ConfirmUser, "get_email_rate_limit_state",
                              return_value=state()), \
                 patch.object(ConfirmUser, "register_email_attempt",
                              return_value=state()), \
                 patch("user.views.send_verification_email",
                       return_value=False) as send:
                for email in (user.email.upper(), "missing@example.invalid"):
                    response = self.client.post(reverse("user:confirm_user"),
                                                {"email": email})
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.context["form"].success_message)
                self.assertEqual(send.call_count, int(not verified))

    @override_settings(DEFAULT_FROM_EMAIL="Configured Sender <sender@example.invalid>")
    def test_branding_fallback_and_expected_email_errors(self) -> None:
        self.assertEqual(get_email_company_name(), "Configured Sender")
        with override_settings(DEFAULT_FROM_EMAIL="sender@example.invalid"):
            self.assertEqual(get_email_company_name(), "sender@example.invalid")
        CompanyProfile.objects.create(name="Active branding")
        self.assertEqual(get_email_company_name(), "Active branding")
        user = User.objects.create_user(email="pending@example.invalid",
                                        is_active=False)
        for exception in (AnymailAPIError("failure"), AnymailRecipientsRefused(),
                          Timeout(), EmailDeliveryError("Message not sent")):
            with patch("user.services.email.send_html_email", side_effect=exception), \
                 self.assertLogs("user.services.email", level="ERROR"):
                self.assertFalse(send_verification_email(RequestFactory().get("/"),
                                                         user))
        with patch("user.services.email.send_html_email", side_effect=TypeError()):
            with self.assertRaises(TypeError):
                send_verification_email(RequestFactory().get("/"), user)

    def test_registration_email_failure_keeps_records_and_redirects(self) -> None:
        member = employee()
        data = {"email": member.email, "password1": "Strong-test-password-842!",
                "password2": "Strong-test-password-842!", "privacy_policy": True}
        with patch("user.views.get_registration_rate_limit_state",
                   return_value=state()), \
             patch("user.mixins.verify_turnstile_token",
                   return_value={"success": True}), \
             patch("user.views.send_verification_email", return_value=False) as send, \
             self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("user:register"), data)
            send.assert_not_called()
        self.assertEqual(response.status_code, 302)
        member.refresh_from_db()
        self.assertIsNotNone(member.user_id)
        self.assertTrue(hasattr(member, "profile"))
        self.assertTrue(list(get_messages(response.wsgi_request)))

    def test_zero_send_result_keeps_registration_and_resend_controlled(self) -> None:
        member = employee()
        data = {
            "email": member.email,
            "password1": "Strong-test-password-842!",
            "password2": "Strong-test-password-842!",
            "privacy_policy": True,
        }
        with (
            patch("core.services.email.EmailMessage.send", return_value=0) as send,
            self.assertLogs("user.services.email", level="ERROR"),
        ):
            with (
                patch(
                    "user.views.get_registration_rate_limit_state",
                    return_value=state(),
                ),
                patch(
                    "user.mixins.verify_turnstile_token",
                    return_value={"success": True},
                ),
                self.captureOnCommitCallbacks(execute=True),
            ):
                response = self.client.post(reverse("user:register"), data)
                send.assert_not_called()

            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, reverse("user:confirm_user"))
            member.refresh_from_db()
            self.assertIsNotNone(member.user_id)
            self.assertFalse(member.user.is_active)
            self.assertFalse(member.user.is_verified)
            self.assertTrue(hasattr(member, "profile"))
            self.assertTrue(list(get_messages(response.wsgi_request)))
            send.assert_called_once_with()

            with (
                patch.object(ConfirmUser, "is_turnstile_valid", return_value=True),
                patch.object(
                    ConfirmUser, "get_email_rate_limit_state", return_value=state()
                ),
                patch.object(
                    ConfirmUser, "register_email_attempt", return_value=state()
                ),
            ):
                response = self.client.post(
                    reverse("user:confirm_user"), {"email": member.email}
                )

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].success_message)
            self.assertEqual(send.call_count, 2)

    def test_password_reset_uses_django_delivery_failure_handling(self) -> None:
        user = User.objects.create_user(email="reset@example.invalid", password="test")
        with patch.object(CustomPasswordResetView, "is_turnstile_valid",
                          return_value=True), \
             patch.object(CustomPasswordResetView, "get_email_rate_limit_state",
                          return_value=state()), \
             patch.object(CustomPasswordResetView, "register_email_attempt",
                          return_value=state()), \
             patch("django.core.mail.EmailMultiAlternatives.send",
                   side_effect=AnymailAPIError("failure")), \
             self.assertLogs("django.contrib.auth", level="ERROR"):
            response = self.client.post(reverse("user:password-reset"),
                                        {"email": user.email.upper()})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("user:password-reset-done"))
