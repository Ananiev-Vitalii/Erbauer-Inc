from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from main.models import CompanyProfile
from user.forms import CustomPasswordResetForm, UserRegistrationForm
from user.models import User
from user.tests.helpers import employee


class IdentityTests(TestCase):
    def test_manager_preserves_case_and_matches_case_insensitively(self) -> None:
        user = User.objects.create_user(email="Mixed@Example.invalid")
        self.assertEqual(user.email, "Mixed@Example.invalid")
        self.assertEqual(User.objects.get_by_natural_key("MIXED@example.invalid"), user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user(email="mixed@example.invalid")

    def test_employee_uniqueness_and_linked_email_sync(self) -> None:
        member = employee()
        user = User.objects.create_user(email=member.email)
        member.user = user
        member.email = "Changed@Example.invalid"
        member.save()
        user.refresh_from_db()
        self.assertEqual(user.email, member.email)
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(member).objects.create(
                position=member.position, email="changed@example.invalid"
            )
        other = User.objects.create_user(email="Other@example.invalid")
        member.email = other.email.upper()
        with self.assertRaises(IntegrityError), transaction.atomic():
            member.save()
        member.refresh_from_db()
        user.refresh_from_db()
        self.assertEqual(user.email, "Changed@Example.invalid")
        self.assertEqual(member.email, user.email)

    def test_registration_matches_employee_and_requires_consent(self) -> None:
        member = employee()
        data = {"email": member.email.upper(), "password1": "Strong-test-password-842!",
                "password2": "Strong-test-password-842!", "privacy_policy": True}
        form = UserRegistrationForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.employee.pk, member.pk)
        data["privacy_policy"] = False
        self.assertIn("privacy_policy", UserRegistrationForm(data).errors)

    def test_reset_only_selects_active_usable_accounts(self) -> None:
        user = User.objects.create_user(email="Mixed@example.invalid", password="test")
        form = CustomPasswordResetForm()
        self.assertEqual(list(form.get_users(user.email.upper())), [user])
        user.is_active = False
        user.save(update_fields=["is_active"])
        self.assertEqual(list(form.get_users(user.email)), [])
        user.is_active = True
        user.set_unusable_password()
        user.save()
        self.assertEqual(list(form.get_users(user.email)), [])

    def test_only_one_company_can_be_active(self) -> None:
        first = CompanyProfile.objects.create(name="First")
        CompanyProfile.objects.create(name="Draft", is_active=False)
        with self.assertRaises(ValidationError):
            CompanyProfile(name="Second").validate_constraints()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CompanyProfile.objects.create(name="Second")
        first.is_active = False
        first.save(update_fields=["is_active"])
        CompanyProfile.objects.create(name="Second")
