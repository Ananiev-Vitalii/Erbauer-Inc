import json
from pathlib import PurePosixPath
from unittest.mock import Mock
from uuid import UUID

from django.templatetags.static import static
from django.test import SimpleTestCase, TestCase

from account.forms import EmployeeContactForm, EmployeeInvoiceForm, ProfileAvatarForm
from account.models import Employee, Profile, profile_directory_path
from account.tests.helpers import address_data
from account.views import UpdateAvatarView
from user.tests.helpers import employee


class ContactValidationTests(TestCase):
    def setUp(self) -> None:
        self.member = employee()

    def contact_form(self, **values: str) -> EmployeeContactForm:
        return EmployeeContactForm(
            {
                **address_data(),
                "email": self.member.email,
                "phone": "6045550123",
                **values,
            },
            instance=self.member,
        )

    def test_phone_accepts_supported_formats_and_saves_canonical_number(self) -> None:
        for value in (
            "6045550123", "604 555 0123", "604-555-0123", "604.555.0123",
            "(604) 555-0123", "+1 (604) 555-0123", "16045550123", "+16045550123",
        ):
            with self.subTest(value=value):
                form = self.contact_form(phone=value)
                self.assertTrue(form.is_valid(), form.errors.as_data())
                self.assertEqual(form.cleaned_data["phone"], "+16045550123")
                form.save()
                self.member.refresh_from_db()
                self.assertEqual(self.member.phone, "+16045550123")
        form = self.contact_form(phone="")
        self.assertTrue(form.is_valid(), form.errors.as_data())
        self.assertEqual(form.cleaned_data["phone"], "")

    def test_invalid_phone_is_rejected_instead_of_repaired_or_truncated(self) -> None:
        for value in (
            "abc6045550123", "６０４５５５０１２３", "60455501234", "+446045550123",
            "604-55-50123", "6045550123 ext 9", "604/555/0123",
        ):
            with self.subTest(value=value):
                self.assertIn("phone", self.contact_form(phone=value).errors)

    def test_both_forms_normalize_supported_postal_codes(self) -> None:
        for value, expected in (
            ("v8m0b6", "V8M 0B6"), ("K1A 0B1", "K1A 0B1"),
            ("x0a0h0", "X0A 0H0"),
        ):
            with self.subTest(value=value):
                forms = (
                    self.contact_form(postal_code=value),
                    EmployeeInvoiceForm({**address_data(), "postal_code": value}),
                )
                for form in forms:
                    self.assertTrue(form.is_valid(), form.errors.as_data())
                    self.assertEqual(form.cleaned_data["postal_code"], expected)
        form = self.contact_form(postal_code="")
        self.assertTrue(form.is_valid(), form.errors.as_data())

    def test_both_forms_reject_forbidden_letters_digits_and_grouping(self) -> None:
        for value in (
            "D1A 1A1", "W1A 1A1", "Z1A 1A1", "A1O 1A1", "A1A-1A1",
            "A 1A1A1", "A1A 1A12", "A１A 1A1", "ſ1A 1A1", "!!!!!!",
        ):
            with self.subTest(value=value):
                self.assertIn(
                    "postal_code", self.contact_form(postal_code=value).errors
                )
                form = EmployeeInvoiceForm({**address_data(), "postal_code": value})
                self.assertIn("postal_code", form.errors)


class AvatarRegressionTests(SimpleTestCase):
    def test_existing_avatar_needs_no_new_uploaded_file(self) -> None:
        profile = Profile(avatar="profiles/existing.png")
        form = ProfileAvatarForm(data={}, files={}, instance=profile)
        self.assertTrue(form.is_valid(), form.errors.as_data())
        self.assertEqual(form.cleaned_data["avatar"].name, "profiles/existing.png")

    def test_missing_avatar_is_valid_and_response_uses_existing_placeholder(
        self,
    ) -> None:
        profile = Profile(avatar="")
        form = ProfileAvatarForm(data={}, files={}, instance=profile)
        self.assertTrue(form.is_valid(), form.errors.as_data())
        response = UpdateAvatarView().form_valid(Mock(save=Mock(return_value=profile)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json.loads(response.content)["avatar_url"],
            static("img/default_profile.png"),
        )

    def test_unsaved_profile_paths_use_uuid4_without_personal_data(self) -> None:
        profile = Profile(employee=Employee(
            email="private@example.invalid", last_name_en="PrivateSurname"
        ))
        paths = [
            profile_directory_path(profile, "PrivateSurname.JPG") for _ in range(2)
        ]
        self.assertIsNone(profile.pk)
        self.assertNotEqual(*paths)
        for name in paths:
            path = PurePosixPath(name)
            self.assertEqual(path.parent.as_posix(), "profiles")
            self.assertEqual(path.suffix, ".jpg")
            self.assertEqual(UUID(hex=path.stem).version, 4)
            self.assertNotIn("private", name.lower())
