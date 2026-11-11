from unittest.mock import Mock, call, patch

from django.core.cache.backends.redis import RedisCache
from django.test import SimpleTestCase
from redis.exceptions import (
    ConnectionError as RedisConnectionError, NoScriptError, ResponseError, TimeoutError,
)

from core.services.rate_limit_redis import (
    SCRIPT, SCRIPT_SHA, RateLimitUnavailable, execute_rate_limit,
)


class RedisRateLimitAdapterTests(SimpleTestCase):
    def setUp(self) -> None:
        self.backend = Mock(spec=RedisCache)
        self.backend.make_and_validate_key.side_effect = lambda key: f"tests:7:{key}"
        self.client = self.backend._cache.get_client.return_value
        self.pool = self.client.connection_pool
        self.connection = self.pool.get_connection.return_value
        self.connection.read_response.return_value = [61, 2]
        self.enterContext(patch("core.services.rate_limit_redis.caches",
                                {"default": self.backend}))

    def execute(self) -> tuple[int, int]:
        return execute_rate_limit(
            keys=["attempt", "block"], operation="register", now=1000,
            attempts_limit=3, window_seconds=17, cooldown_seconds=29,
        )

    def test_existing_pool_namespace_and_raw_arguments(self) -> None:
        self.assertEqual(self.execute(), (61, 2))
        self.backend._cache.get_client.assert_called_once_with(write=True)
        self.connection.send_command.assert_called_once_with(
            "EVALSHA", SCRIPT_SHA, 2, "tests:7:attempt", "tests:7:block",
            "register", 1000, 3, 17, 29,
        )
        self.pool.release.assert_called_once_with(self.connection)
        self.connection.disconnect.assert_not_called()

    def test_noscript_falls_back_once_to_eval(self) -> None:
        self.connection.read_response.side_effect = [NoScriptError(), [0, 0]]
        self.assertEqual(self.execute(), (0, 0))
        arguments = (2, "tests:7:attempt", "tests:7:block", "register", 1000, 3, 17, 29)
        self.assertEqual(self.connection.send_command.call_args_list, [
            call("EVALSHA", SCRIPT_SHA, *arguments), call("EVAL", SCRIPT, *arguments)
        ])
        self.pool.release.assert_called_once_with(self.connection)

    def test_ambiguous_send_or_response_timeout_is_never_retried(self) -> None:
        for boundary in ("send_command", "read_response"):
            with self.subTest(boundary=boundary):
                self.connection.reset_mock()
                getattr(self.connection, boundary).side_effect = TimeoutError()
                with self.assertLogs("core.services.rate_limit_redis", level="ERROR"):
                    with self.assertRaises(RateLimitUnavailable):
                        self.execute()
                self.connection.send_command.assert_called_once()
                self.connection.disconnect.assert_called_once()
                getattr(self.connection, boundary).side_effect = None
        self.assertEqual(self.pool.release.call_count, 2)

    def test_eval_timeout_after_noscript_does_not_repeat_the_mutation(self) -> None:
        self.connection.read_response.side_effect = [NoScriptError(), TimeoutError()]
        with self.assertLogs("core.services.rate_limit_redis", level="ERROR"):
            with self.assertRaises(RateLimitUnavailable):
                self.execute()
        commands = [entry.args[0]
                    for entry in self.connection.send_command.call_args_list]
        self.assertEqual(commands, ["EVALSHA", "EVAL"])
        self.connection.disconnect.assert_called_once()
        self.pool.release.assert_called_once_with(self.connection)

    def test_connection_and_permission_errors_are_sanitized(self) -> None:
        for error in (RedisConnectionError("test-sensitive-marker"),
                      ResponseError("NOPERM test-sensitive-marker")):
            with self.subTest(error=type(error).__name__):
                self.connection.read_response.side_effect = error
                with self.assertLogs("core.services.rate_limit_redis",
                                     level="ERROR") as logs:
                    with self.assertRaises(RateLimitUnavailable) as raised:
                        self.execute()
                self.assertIs(raised.exception.__cause__, error)
                self.assertNotIn("test-sensitive-marker", str(raised.exception))
                self.assertNotIn("test-sensitive-marker", " ".join(logs.output))

    def test_failure_before_acquiring_a_connection_has_no_retry(self) -> None:
        self.backend._cache.get_client.side_effect = RedisConnectionError()
        with self.assertLogs("core.services.rate_limit_redis", level="ERROR"):
            with self.assertRaises(RateLimitUnavailable):
                self.execute()
        self.backend._cache.get_client.assert_called_once_with(write=True)
        self.pool.release.assert_not_called()

    def test_lua_and_wrongtype_errors_are_not_hidden_as_provider_failures(self) -> None:
        for message in ("user_script:1: test error", "Error compiling script",
                        "WRONGTYPE Operation against a key"):
            with self.subTest(message=message):
                error = ResponseError(message)
                self.connection.read_response.side_effect = error
                with self.assertRaises(ResponseError) as raised:
                    self.execute()
                self.assertIs(raised.exception, error)

    def test_programming_errors_propagate_and_connection_is_released(self) -> None:
        self.connection.read_response.side_effect = ValueError("test error")
        with self.assertRaises(ValueError):
            self.execute()
        self.pool.release.assert_called_once_with(self.connection)

    def test_non_redis_backend_fails_closed(self) -> None:
        with patch("core.services.rate_limit_redis.caches", {"default": object()}):
            with self.assertLogs("core.services.rate_limit_redis", level="ERROR"):
                with self.assertRaises(RateLimitUnavailable):
                    self.execute()
        self.backend._cache.get_client.assert_not_called()
