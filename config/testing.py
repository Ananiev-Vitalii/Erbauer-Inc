"""Small safety boundary around Django's standard backend test runner."""

import socket
from collections.abc import Iterable
from contextlib import ExitStack
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.backends.postgresql.base import DatabaseWrapper
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


def _block_external_operation(*args: object, **kwargs: object) -> None:
    raise RuntimeError("External operation blocked; mock this boundary in the test.")


class IsolatedDiscoverRunner(DiscoverRunner):
    """Use normal Django discovery and database handling with local-only guards."""

    def run_tests(self, test_labels: Iterable[str], **kwargs: Any) -> int:
        if settings.SETTINGS_MODULE != "config.settings.test":
            raise ImproperlyConfigured("The isolated runner requires test settings.")
        if self.parallel not in {0, 1}:
            raise ImproperlyConfigured("This initial test setup supports serial runs.")

        database = settings.DATABASES["default"]
        expected = {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": "127.0.0.1",
            "PORT": "55432",
            "NAME": "erbauer_test_control",
            "USER": "erbauer_test",
            "PASSWORD": "erbauer_test_only",
        }
        if (
            set(settings.DATABASES) != {"default"}
            or any(database.get(key) != value for key, value in expected.items())
            or database.get("TEST", {}).get("NAME") != "test_erbauer_backend"
            or database.get("OPTIONS", {}).get("hostaddr") != "127.0.0.1"
        ):
            raise ImproperlyConfigured("Unexpected database configuration for tests.")

        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        original_getaddrinfo = socket.getaddrinfo
        original_database_connect = DatabaseWrapper.get_new_connection

        def database_connect(
            backend: DatabaseWrapper, parameters: dict[str, Any]
        ) -> Any:
            # libpq uses native sockets and does not pass through Python's guard.
            if (
                parameters.get("host") != "127.0.0.1"
                or parameters.get("hostaddr") != "127.0.0.1"
                or str(parameters.get("port")) != "55432"
                or parameters.get("user") != "erbauer_test"
                or parameters.get("password") != "erbauer_test_only"
                or parameters.get("dbname") not in {
                    "postgres", "erbauer_test_control", "test_erbauer_backend"
                }
                or "service" in parameters
            ):
                raise RuntimeError("Non-test PostgreSQL connection blocked.")
            return original_database_connect(backend, parameters)

        def check_address(address: object) -> None:
            if not (
                settings.TEST_REDIS_INTEGRATION
                and isinstance(address, tuple)
                and len(address) == 2
                and address == ("127.0.0.1", 56379)
            ):
                raise RuntimeError("Network access blocked by the backend test runner.")

        def connect(sock: socket.socket, address: tuple[str, int]) -> None:
            check_address(address)
            return original_connect(sock, address)

        def connect_ex(sock: socket.socket, address: tuple[str, int]) -> int:
            check_address(address)
            return original_connect_ex(sock, address)

        def getaddrinfo(host: str, port: int, *args, **options) -> list[tuple]:
            check_address((host, port))
            return original_getaddrinfo(host, port, *args, **options)

        with ExitStack() as stack:
            media_root = stack.enter_context(
                TemporaryDirectory(prefix="erbauer-backend-tests-")
            )
            stack.enter_context(override_settings(MEDIA_ROOT=media_root))
            stack.enter_context(
                patch.object(
                    DatabaseWrapper, "get_new_connection", new=database_connect
                )
            )
            for target, replacement in (
                ("socket.socket.connect", connect),
                ("socket.socket.connect_ex", connect_ex),
                ("socket.getaddrinfo", getaddrinfo),
            ):
                stack.enter_context(patch(target, new=replacement))

            for target in (
                "celery.app.task.Task.apply_async",
                "celery.app.base.Celery.send_task",
                "requests.sessions.Session.request",
                "urllib3.PoolManager.request",
                "subprocess.Popen",
            ):
                stack.enter_context(
                    patch(target, side_effect=_block_external_operation)
                )

            # This field has explicit storage, so STORAGES alone cannot isolate it.
            for method in ("open", "save", "delete", "exists", "url", "size"):
                stack.enter_context(
                    patch(
                        f"account.storage.PrivateInvoiceCloudinaryStorage.{method}",
                        side_effect=_block_external_operation,
                    )
                )

            return super().run_tests(test_labels, **kwargs)
