from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from user.services.rate_limits import login, password_reset, resend_verification
from user.tests.helpers import state


class RateLimitTests(SimpleTestCase):
    def test_workflows_keep_captcha_fields_separate(self) -> None:
        request = RequestFactory().post("/", {"username": "Mixed@example.invalid"})
        workflows = (
            (login, login.get_login_rate_limit_state, login.register_login_attempt,
             login.register_login_captcha_failure, (request,), "user_login"),
            (password_reset, password_reset.get_password_reset_rate_limit_state,
             password_reset.register_password_reset_attempt,
             password_reset.register_password_reset_captcha_failure,
             (request, "Mixed@example.invalid"), "user_password_reset"),
            (resend_verification,
             resend_verification.get_resend_verification_rate_limit_state,
             resend_verification.register_resend_verification_attempt,
             resend_verification.register_resend_verification_captcha_failure,
             (request, "Mixed@example.invalid"), "user_resend_verification"),
        )
        for module, read, register, captcha, args, scope in workflows:
            with self.subTest(scope=scope), \
                 patch.object(module, "get_rate_limit_state",
                              return_value=state()) as get, \
                 patch.object(module, "register_rate_limit_attempt",
                              return_value=state()) as write:
                read(*args)
                self.assertEqual(get.call_args.kwargs["scope"], scope)
                self.assertEqual([f.name for f in get.call_args.kwargs["fields"]],
                                 ["ip", "email", "captcha_ip"])
                register(*args)
                ordinary = write.call_args.kwargs
                self.assertEqual([f.name for f in ordinary["fields"]], ["ip", "email"])
                captcha(request)
                failure = write.call_args.kwargs
                self.assertEqual([f.name for f in failure["fields"]], ["captcha_ip"])
                for key in ("scope", "attempts_limit", "window_seconds",
                            "cooldown_seconds"):
                    self.assertEqual(ordinary[key], failure[key])

    def test_login_reset_includes_captcha_counter(self) -> None:
        with patch.object(login, "reset_rate_limit") as reset:
            login.reset_login_rate_limit(
                RequestFactory().post("/", {"username": "a@example.invalid"})
            )
        self.assertEqual([f.name for f in reset.call_args.kwargs["fields"]],
                         ["ip", "email", "captcha_ip"])
