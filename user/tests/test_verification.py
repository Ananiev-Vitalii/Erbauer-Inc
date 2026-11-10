from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from user.models import User
from user.services.tokens import token_generator
from user.views import verify_user


class VerificationTests(TestCase):
    def test_only_pending_user_is_activated(self) -> None:
        for active, verified in ((False, False), (False, True), (True, False),
                                 (True, True)):
            with self.subTest(active=active, verified=verified):
                user = User.objects.create_user(
                    email=f"user-{active}-{verified}@example.invalid",
                    is_active=active, is_verified=verified,
                )
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = token_generator.make_token(user)
                with patch("user.views.login") as login:
                    response = verify_user(RequestFactory().get("/"), uid, token)
                user.refresh_from_db()
                pending = not active and not verified
                self.assertEqual(login.call_count, int(pending))
                self.assertEqual(user.is_active, active or pending)
                self.assertEqual(user.is_verified, verified or pending)
                self.assertEqual(response.status_code, 302)

    def test_invalid_expired_and_used_tokens_do_not_log_in(self) -> None:
        user = User.objects.create_user(email="pending@example.invalid",
                                        is_active=False)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        with patch("user.views.login") as login:
            for bad_uid, bad_token in (("!", token), (uid, "invalid")):
                response = verify_user(RequestFactory().get("/"), bad_uid, bad_token)
                self.assertIn("verify/invalid", response.url)
            with patch.object(token_generator, "_num_seconds", return_value=10**12):
                response = verify_user(RequestFactory().get("/"), uid, token)
                self.assertIn("verify/invalid", response.url)
            login.assert_not_called()
            verify_user(RequestFactory().get("/"), uid, token)
            verify_user(RequestFactory().get("/"), uid, token)
            login.assert_called_once()
