from unittest.mock import Mock, patch

from django.db import IntegrityError, transaction
from django.test import TestCase

from account.models import Profile
from user.models import User
from user.services.registration import RegistrationConflict, register_employee_user
from user.tests.helpers import employee, pg_conflict, prepared_user


class RegistrationTests(TestCase):
    def setUp(self) -> None:
        self.employee = employee()

    def test_registration_defers_callback_until_commit(self) -> None:
        callback = Mock()
        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            user = register_employee_user(
                employee_id=self.employee.pk, user=prepared_user(), on_created=callback
            )
            callback.assert_not_called()
        verification_callbacks = [
            pending for pending in callbacks
            if pending.__module__ == "user.services.registration"
        ]
        self.assertEqual(len(verification_callbacks), 1)
        callback.assert_not_called()
        for pending in callbacks:
            pending()
        callback.assert_called_once_with(user)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.user_id, user.pk)
        self.assertTrue(Profile.objects.filter(employee=self.employee).exists())
        self.assertEqual(user.email, self.employee.email)
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_verified)

    def test_stale_employee_states_are_rejected(self) -> None:
        for updates in ({"is_active": False}, {"email": "changed@example.invalid"}):
            with self.subTest(updates=updates), transaction.atomic():
                type(self.employee).objects.filter(
                    pk=self.employee.pk
                ).update(**updates)
                with self.assertRaises(RegistrationConflict):
                    register_employee_user(
                        employee_id=self.employee.pk, user=prepared_user(),
                        on_created=Mock()
                    )
                transaction.set_rollback(True)
        self.assertFalse(User.objects.exists())

    def test_partial_registration_rolls_back_without_callback(self) -> None:
        callback = Mock()
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with patch("user.services.registration.Profile.objects.create",
                       side_effect=RuntimeError("Synthetic failure")):
                with self.assertRaises(RuntimeError):
                    register_employee_user(
                        employee_id=self.employee.pk, user=prepared_user(),
                        on_created=callback
                    )
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.user_id)
        self.assertFalse(User.objects.exists())
        self.assertFalse(callbacks)
        callback.assert_not_called()

    def test_only_known_email_constraint_errors_are_translated(self) -> None:
        for constraint in ("user_email_lower_unique", "user_user_email_key",
                           "user_user_pkey"):
            with self.subTest(constraint=constraint):
                error = IntegrityError("Synthetic conflict")
                error.__cause__ = pg_conflict(constraint)
                expected = (
                    IntegrityError if constraint.endswith("pkey")
                    else RegistrationConflict
                )
                with patch.object(User, "save", side_effect=error):
                    with self.assertRaises(expected):
                        register_employee_user(
                            employee_id=self.employee.pk, user=prepared_user(),
                            on_created=Mock()
                        )

    def test_existing_user_and_employee_link_are_rejected(self) -> None:
        existing = User.objects.create_user(email=self.employee.email)
        for linked in (False, True):
            with self.subTest(linked=linked):
                if linked:
                    self.employee.user = existing
                    self.employee.save(update_fields=["user"])
                with self.assertRaises(RegistrationConflict):
                    register_employee_user(
                        employee_id=self.employee.pk, user=prepared_user(),
                        on_created=Mock()
                    )
        self.assertEqual(User.objects.count(), 1)
