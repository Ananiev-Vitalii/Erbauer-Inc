from unittest.mock import patch

from django.test import SimpleTestCase

from core.services.rate_limit import (
    RateLimitField, get_rate_limit_state, register_rate_limit_attempt, reset_rate_limit,
)
from core.services.rate_limit_redis import RateLimitUnavailable


class RateLimitServiceTests(SimpleTestCase):
    def setUp(self) -> None:
        self.execute = self.enterContext(
            patch("core.services.rate_limit.execute_rate_limit", return_value=(0, 0))
        )
        self.enterContext(patch("core.services.rate_limit.time", return_value=1000))

    def test_normalization_and_triggered_field_mapping(self) -> None:
        self.execute.return_value = (61, 2)
        state = get_rate_limit_state(
            scope="test", fields=[RateLimitField("empty", None),
                                  RateLimitField("email", " User@Example.INVALID "),
                                  RateLimitField("name", " Straße ")],
            attempts_limit=5,
        )
        self.execute.assert_called_once_with(
            keys=["rate_limit:v2:test:attempt:email:user@example.invalid",
                  "rate_limit:v2:test:block:email:user@example.invalid",
                  "rate_limit:v2:test:attempt:name:strasse",
                  "rate_limit:v2:test:block:name:strasse"],
            operation="read", now=1000, attempts_limit=5,
            window_seconds=0, cooldown_seconds=0,
        )
        self.assertTrue(state.blocked)
        self.assertEqual(state.remaining_seconds, 61)
        self.assertEqual(state.remaining_minutes, 2)
        self.assertEqual(state.triggered_by, "name")
        self.assertEqual(state.attempts_limit, 5)

    def test_register_forwards_window_and_cooldown_and_keeps_zero_value(self) -> None:
        state = register_rate_limit_attempt(
            scope="contact", fields=[RateLimitField("id", 0)], attempts_limit=3,
            window_seconds=17, cooldown_seconds=29,
        )
        arguments = self.execute.call_args.kwargs
        self.assertEqual(arguments["operation"], "register")
        self.assertEqual(arguments["window_seconds"], 17)
        self.assertEqual(arguments["cooldown_seconds"], 29)
        self.assertEqual(arguments["keys"], [
            "rate_limit:v2:contact:attempt:id:0", "rate_limit:v2:contact:block:id:0"
        ])
        self.assertFalse(state.blocked)
        self.assertIsNone(state.triggered_by)

    def test_empty_fields_do_not_call_storage(self) -> None:
        state = get_rate_limit_state(
            scope="test", fields=[RateLimitField("none", None),
                                  RateLimitField("blank", "  ")], attempts_limit=3,
        )
        self.assertFalse(state.blocked)
        self.assertEqual(state.remaining_seconds, 0)
        self.execute.assert_not_called()

    def test_reset_uses_the_same_normalized_attempt_and_block_keys(self) -> None:
        self.assertIsNone(reset_rate_limit(
            scope="test", fields=[RateLimitField("email", " USER@example.invalid ")]
        ))
        self.assertEqual(self.execute.call_args.kwargs["operation"], "reset")
        self.assertEqual(self.execute.call_args.kwargs["keys"], [
            "rate_limit:v2:test:attempt:email:user@example.invalid",
            "rate_limit:v2:test:block:email:user@example.invalid",
        ])

    def test_scopes_are_isolated_and_storage_failures_propagate(self) -> None:
        for scope in ("login", "contact"):
            get_rate_limit_state(scope=scope,
                                 fields=[RateLimitField("ip", "192.0.2.1")],
                                 attempts_limit=3)
        first, second = self.execute.call_args_list
        self.assertNotEqual(first.kwargs["keys"], second.kwargs["keys"])
        self.execute.side_effect = RateLimitUnavailable("test unavailable")
        with self.assertRaises(RateLimitUnavailable):
            get_rate_limit_state(scope="contact", fields=[RateLimitField("ip", "x")],
                                 attempts_limit=3)
