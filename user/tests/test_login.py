from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from core.services.rate_limit_redis import RateLimitUnavailable
from user.forms import UserAuthenticationForm
from user.models import User
from user.tests.helpers import state


class LoginTests(TestCase):
    def setUp(self) -> None:
        self.data = {"username": "person@example.invalid", "password": "Secret-842!"}

    def test_display_only_form_never_authenticates_or_echoes_password(self) -> None:
        form = UserAuthenticationForm(
            data=self.data, allow_authentication=False, service_message="CAPTCHA failed"
        )
        with patch("django.contrib.auth.forms.authenticate") as authenticate:
            self.assertFalse(form.is_valid())
            html = form.as_p()
        authenticate.assert_not_called()
        self.assertNotIn(self.data["password"], html)

    def test_failed_captcha_only_counts_captcha_ip_during_full_render(self) -> None:
        with patch("user.views.get_login_rate_limit_state", return_value=state()), \
             patch("user.mixins.verify_turnstile_token",
                   return_value={"success": False}), \
             patch("user.views.register_login_captcha_failure",
                   return_value=state()) as captcha, \
             patch("user.views.register_login_attempt") as attempts, \
             patch("django.contrib.auth.forms.authenticate") as authenticate:
            response = self.client.post(reverse("user:login"), self.data)
        self.assertEqual(response.status_code, 200)
        captcha.assert_called_once()
        attempts.assert_not_called()
        authenticate.assert_not_called()
        self.assertNotIn(self.data["password"].encode(), response.content)

    def test_initial_and_concurrent_blocking_skip_authentication(self) -> None:
        for states, calls in (([state(True)], 0), ([state(), state(True)], 1)):
            with self.subTest(calls=calls), \
                 patch("user.views.get_login_rate_limit_state", side_effect=states), \
                 patch("user.mixins.verify_turnstile_token",
                       return_value={"success": True}) as cloud, \
                 patch("user.views.register_login_captcha_failure") as captcha, \
                 patch("user.views.register_login_attempt") as attempts, \
                 patch("django.contrib.auth.forms.authenticate") as authenticate:
                response = self.client.post(reverse("user:login"), self.data)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(cloud.call_count, calls)
                captcha.assert_not_called()
                attempts.assert_not_called()
                authenticate.assert_not_called()

    def test_invalid_credentials_only_count_business_attempt(self) -> None:
        with patch("user.views.get_login_rate_limit_state", return_value=state()), \
             patch("user.mixins.verify_turnstile_token",
                   return_value={"success": True}), \
             patch("user.views.register_login_attempt",
                   return_value=state()) as attempts, \
             patch("user.views.register_login_captcha_failure") as captcha:
            response = self.client.post(reverse("user:login"), self.data)
        self.assertEqual(response.status_code, 200)
        attempts.assert_called_once()
        captcha.assert_not_called()

    def test_success_resets_before_session_and_reset_failure_prevents_login(
        self,
    ) -> None:
        User.objects.create_user(email=self.data["username"],
                                 password=self.data["password"])
        for unavailable in (True, False):
            def reset(request: object) -> None:
                self.assertNotIn("_auth_user_id", self.client.session)
                if unavailable:
                    raise RateLimitUnavailable("Synthetic failure")

            with self.subTest(unavailable=unavailable), \
                 patch("user.views.get_login_rate_limit_state", return_value=state()), \
                 patch("user.mixins.verify_turnstile_token",
                       return_value={"success": True}), \
                 patch("user.views.reset_login_rate_limit", side_effect=reset):
                response = self.client.post(reverse("user:login"), self.data)
                self.assertEqual(response.status_code, 503 if unavailable else 302)
                self.assertEqual("_auth_user_id" in self.client.session,
                                 not unavailable)
