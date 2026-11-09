from itertools import product

from django.test import SimpleTestCase

from main.forms import ContactForm
from main.tests.helpers import contact_data


class ContactFormTests(SimpleTestCase):
    def test_allowed_phone_formats_are_normalized(self) -> None:
        national_numbers = (
            "6045550123", "604 555 0123", "604-555-0123",
            "604.555.0123", "(604) 555-0123",
        )
        prefixes = ("", "+1", "+1 ", "1", "1 ")
        for prefix, national in product(prefixes, national_numbers):
            phone = prefix + national
            with self.subTest(phone=phone):
                form = ContactForm({**contact_data(), "phone": phone})
                self.assertTrue(form.is_valid(), form.errors.as_data())
                self.assertEqual(form.cleaned_data["phone"], "+16045550123")

    def test_invalid_phone_content_and_grouping_are_rejected(self) -> None:
        for phone in (
            "604555012", "60455501234", "+1 16045550123",
            "604-555.0123", "60 4555 0123", "604/555/0123",
            "(604)555-0123", "(6045550123)", "+1  6045550123",
            "6045550123x", "6045550123 ext 9", "abc6045550123",
            "٦٠٤٥٥٥٠١٢٣", "６０４５５５０１２３", "+44 20 7946 0958",
            "604\t555\t0123", "604\n555\n0123", "604_555_0123",
            "604\u00a0555\u00a00123",
        ):
            with self.subTest(phone=phone):
                form = ContactForm({**contact_data(), "phone": phone})
                self.assertFalse(form.is_valid())
                self.assertIn("phone", form.errors)

    def test_outer_whitespace_is_stripped(self) -> None:
        form = ContactForm({**contact_data(), "phone": " 6045550123 "})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["phone"], "+16045550123")

    def test_required_fields_and_explicit_false_consent_are_rejected(self) -> None:
        for field in contact_data():
            with self.subTest(field=field):
                data = contact_data()
                del data[field]
                form = ContactForm(data)
                self.assertFalse(form.is_valid())
                self.assertEqual(form.errors.as_data()[field][0].code, "required")
        form = ContactForm({**contact_data(), "privacy_policy": False})
        self.assertFalse(form.is_valid())
        self.assertIn("privacy_policy", form.errors)

    def test_length_limits_and_blank_text(self) -> None:
        form = ContactForm({**contact_data(), "name": "n" * 50,
                            "message": "m" * 1000,
                            "phone": "+1 (604) 555-0123"})
        self.assertTrue(form.is_valid())
        for field, value in (
            ("name", "n" * 51), ("message", "m" * 1001),
            ("phone", "1" * 18), ("name", "   "), ("message", "   "),
        ):
            with self.subTest(field=field, value_length=len(value)):
                form = ContactForm({**contact_data(), field: value})
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
