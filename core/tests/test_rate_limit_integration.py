from concurrent.futures import ThreadPoolExecutor
from time import monotonic, sleep
from unittest import skipUnless
from uuid import uuid4

from django.conf import settings
from django.core.cache import caches
from django.test import SimpleTestCase, override_settings, tag

from core.services.rate_limit import (
    RateLimitField, RateLimitState, get_rate_limit_state,
    register_rate_limit_attempt, reset_rate_limit,
)


@tag("redis")
@skipUnless(settings.TEST_REDIS_INTEGRATION, "Local Redis integration is opt-in.")
class RedisRateLimitIntegrationTests(SimpleTestCase):
    def setUp(self) -> None:
        configuration = {
            **settings.TEST_REDIS_CACHE,
            "KEY_PREFIX": f"erbauer:tests:{uuid4().hex}",
        }
        self.assertEqual(configuration["LOCATION"], "redis://127.0.0.1:56379/0")
        self.enterContext(override_settings(CACHES={"default": configuration}))
        self.backend = caches["default"]
        self.client = self.backend._cache.get_client(write=True)
        self.addCleanup(self.client.connection_pool.disconnect)
        self.client.ping()
        self.scope = f"integration-{uuid4().hex}"
        self.fields = [RateLimitField("ip", "192.0.2.1"),
                       RateLimitField("email", "visitor@example.invalid")]
        self.keys = self.track_keys(self.scope)

    def track_keys(self, scope: str) -> list[str]:
        logical_keys = [f"rate_limit:v2:{scope}:{kind}:{field.name}:{field.value}"
                        for field in self.fields for kind in ("attempt", "block")]
        physical_keys = [self.backend.make_and_validate_key(key)
                         for key in logical_keys]
        self.addCleanup(self.client.delete, *physical_keys)
        return physical_keys

    def register(
        self, *, scope: str | None = None, limit: int = 3,
        window: int = 60, cooldown: int = 30,
    ) -> RateLimitState:
        return register_rate_limit_attempt(
            scope=scope or self.scope, fields=self.fields, attempts_limit=limit,
            window_seconds=window, cooldown_seconds=cooldown,
        )

    def read(self) -> RateLimitState:
        return get_rate_limit_state(
            scope=self.scope, fields=self.fields, attempts_limit=3
        )

    def wait_for_expiry(self, keys: list[str]) -> None:
        deadline = monotonic() + 3
        while self.client.exists(*keys) and monotonic() < deadline:
            sleep(0.01)
        self.assertEqual(self.client.exists(*keys), 0)

    def test_threshold_blocks_all_fields_without_extending_cooldown(self) -> None:
        self.assertFalse(self.register().blocked)
        self.assertFalse(self.register().blocked)
        state = self.register()
        self.assertTrue(state.blocked)
        self.assertEqual(state.triggered_by, "ip")
        self.assertEqual(state.remaining_seconds, 30)
        self.assertEqual(self.client.mget(self.keys[::2]), [None, None])
        self.assertEqual(self.client.get(self.keys[1]), self.client.get(self.keys[3]))
        for key in self.keys[1::2]:
            self.assertGreater(self.client.ttl(key), 0)
            self.assertLessEqual(self.client.ttl(key), 30)
            self.client.pexpire(key, 2000)
        self.assertTrue(self.register().blocked)
        for key in self.keys[1::2]:
            self.assertLessEqual(self.client.pttl(key), 2000)

    def test_attempt_window_is_renewed_for_every_field(self) -> None:
        self.register(limit=10)
        for key in self.keys[::2]:
            self.client.pexpire(key, 1000)
        self.register(limit=10)
        for key in self.keys[::2]:
            self.assertEqual(self.client.get(key), b"2")
            self.assertGreater(self.client.ttl(key), 50)
            self.assertLessEqual(self.client.ttl(key), 60)

    def test_read_does_not_create_attempts_or_extend_the_window(self) -> None:
        self.assertFalse(self.read().blocked)
        self.assertEqual(self.client.exists(*self.keys), 0)
        self.register(limit=10)
        for key in self.keys[::2]:
            self.client.pexpire(key, 1000)
        self.assertFalse(self.read().blocked)
        for key in self.keys[::2]:
            self.assertEqual(self.client.get(key), b"1")
            self.assertLessEqual(self.client.pttl(key), 1000)

    def test_attempt_expiry_starts_a_new_window(self) -> None:
        self.register(window=1)
        self.wait_for_expiry(self.keys[::2])
        self.assertFalse(self.register(window=1).blocked)
        self.assertEqual(self.client.mget(self.keys[::2]), [b"1", b"1"])

    def test_cooldown_expiry_allows_a_new_attempt(self) -> None:
        self.assertTrue(self.register(limit=1, cooldown=1).blocked)
        self.wait_for_expiry(self.keys[1::2])
        self.assertFalse(self.read().blocked)
        self.assertFalse(self.register().blocked)
        self.assertEqual(self.client.mget(self.keys[::2]), [b"1", b"1"])

    def test_threshold_on_second_field_also_blocks_the_first(self) -> None:
        self.client.set(self.keys[2], 2, ex=60)
        state = self.register()
        self.assertTrue(state.blocked)
        self.assertEqual(state.triggered_by, "email")
        self.assertIsNotNone(self.client.get(self.keys[1]))
        self.assertIsNotNone(self.client.get(self.keys[3]))
        self.assertEqual(self.client.mget(self.keys[::2]), [None, None])

    def test_reset_is_scoped_and_preserves_unrelated_keys(self) -> None:
        other_scope = f"integration-other-{uuid4().hex}"
        other_keys = self.track_keys(other_scope)
        self.register(limit=1)
        self.register(scope=other_scope)
        reset_rate_limit(scope=self.scope, fields=self.fields)
        self.assertEqual(self.client.mget(self.keys), [None] * 4)
        self.assertEqual(self.client.mget(other_keys[::2]), [b"1", b"1"])
        self.assertFalse(self.read().blocked)
        self.assertFalse(self.register().blocked)

    def test_concurrent_requests_cannot_pass_the_threshold(self) -> None:
        def attempt(number: int) -> RateLimitState:
            backend = caches["default"]
            try:
                return self.register(limit=8, cooldown=45)
            finally:
                backend._cache.get_client(write=True).connection_pool.disconnect()

        with ThreadPoolExecutor(max_workers=8) as executor:
            states = list(executor.map(attempt, range(24)))
        self.assertEqual(sum(not state.blocked for state in states), 7)
        self.assertTrue(self.read().blocked)
        self.assertEqual(self.client.mget(self.keys[::2]), [None, None])
        self.assertEqual(self.client.get(self.keys[1]), self.client.get(self.keys[3]))
