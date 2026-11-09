from unittest.mock import patch

from django.test import TestCase, override_settings

from main.services.email import send_contact_email
from main.tests.helpers import create_company


@override_settings(COMPANY_CONTACT_EMAIL="recipient@example.invalid")
class ContactEmailServiceTests(TestCase):
    def test_payload_contains_contact_data_and_latest_active_company(self) -> None:
        create_company("Older company")
        active = create_company("Current company")
        create_company("Inactive company", active=False)
        data = {"name": "Visitor", "phone": "+16045550123", "message": "Question"}
        with patch("main.services.email.send_html_email") as send:
            send_contact_email(data)
        send.assert_called_once()
        payload = send.call_args.args[0]
        self.assertEqual(payload.to, ["recipient@example.invalid"])
        self.assertEqual(payload.context["company_base"].pk, active.pk)
        for key, value in data.items():
            self.assertEqual(payload.context[key], value)

    def test_missing_company_is_allowed_and_provider_failure_propagates(self) -> None:
        with patch("main.services.email.send_html_email") as send:
            send_contact_email({})
            self.assertIsNone(send.call_args.args[0].context["company_base"])
            send.side_effect = RuntimeError("test delivery failure")
            with self.assertRaises(RuntimeError):
                send_contact_email({})
