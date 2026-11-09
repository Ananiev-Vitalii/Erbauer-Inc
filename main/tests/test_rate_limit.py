from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from core.services.rate_limit import RateLimitField, RateLimitState
from main.services import rate_limit


@override_settings(CLIENT_IP_SOURCE="remote_addr")
class ContactRateLimitServiceTests(SimpleTestCase):
    def test_read_and_register_use_the_same_scope_ip_and_module_constants(self) -> None:
        request = RequestFactory().post("/contact/submit/", REMOTE_ADDR="192.0.2.1")
        state = RateLimitState(False, 0, 0, 4)
        with (
            patch.object(rate_limit, "ATTEMPTS", 4),
            patch.object(rate_limit, "WINDOW_SECONDS", 17),
            patch.object(rate_limit, "COOLDOWN_SECONDS", 29),
            patch.object(rate_limit, "get_rate_limit_state",
                         return_value=state) as read,
            patch.object(rate_limit, "register_rate_limit_attempt",
                         return_value=state) as register,
        ):
            self.assertIs(rate_limit.get_contact_form_rate_limit_state(request), state)
            self.assertIs(rate_limit.register_contact_form_attempt(request), state)
            arguments = {
                "scope": "main_contact_form",
                "fields": [RateLimitField("ip", "192.0.2.1")],
                "attempts_limit": 4,
            }
            read.assert_called_once_with(**arguments)
            register.assert_called_once_with(
                **arguments, window_seconds=17, cooldown_seconds=29
            )

    def test_missing_ip_uses_a_shared_no_ip_bucket(self) -> None:
        request = RequestFactory().post("/contact/submit/", REMOTE_ADDR="invalid")
        with patch.object(rate_limit, "register_rate_limit_attempt") as register:
            rate_limit.register_contact_form_attempt(request)
        self.assertEqual(register.call_args.kwargs["fields"],
                         [RateLimitField("ip", "no-ip")])
