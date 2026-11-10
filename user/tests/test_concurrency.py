from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock, patch

from django.db import close_old_connections, connection, connections, transaction
from django.test import RequestFactory, TransactionTestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from account.models import Profile
from user.models import User
from user.services.registration import RegistrationConflict, register_employee_user
from user.services.tokens import token_generator
from user.tests.helpers import employee, prepared_user
from user.views import verify_user


class ConcurrencyTests(TransactionTestCase):
    def setUp(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row locks are required.")

    def test_parallel_registration_creates_one_account_and_callback(self) -> None:
        member = employee()
        barrier = Barrier(2, timeout=10)
        callback = Mock()

        def register() -> bool:
            close_old_connections()
            try:
                user = prepared_user()
                barrier.wait()
                try:
                    register_employee_user(
                        employee_id=member.pk, user=user, on_created=callback
                    )
                except RegistrationConflict:
                    return False
                return True
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: register(), range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Profile.objects.count(), 1)
        member.refresh_from_db()
        self.assertEqual(member.user_id, User.objects.get().pk)
        callback.assert_called_once()

    def test_parallel_verification_logs_in_only_once(self) -> None:
        user = User.objects.create_user(email="pending@example.invalid",
                                        is_active=False)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        barrier = Barrier(2, timeout=10)

        def verify() -> int:
            close_old_connections()
            try:
                barrier.wait()
                return verify_user(RequestFactory().get("/"), uid, token).status_code
            finally:
                connections.close_all()

        with (
            patch("user.views.login") as login,
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            self.assertEqual(list(pool.map(lambda _: verify(), range(2))), [302, 302])
        login.assert_called_once()
        user.refresh_from_db()
        self.assertTrue(user.is_active and user.is_verified)

    def test_callback_waits_for_outer_commit_and_is_discarded_on_rollback(self) -> None:
        member = employee()
        callback = Mock()
        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                register_employee_user(
                    employee_id=member.pk, user=prepared_user(), on_created=callback
                )
                callback.assert_not_called()
                raise RuntimeError("Abort outer transaction")
        callback.assert_not_called()
        self.assertFalse(User.objects.exists())
        with transaction.atomic():
            user = register_employee_user(
                employee_id=member.pk, user=prepared_user(), on_created=callback
            )
            callback.assert_not_called()
        callback.assert_called_once_with(user)
