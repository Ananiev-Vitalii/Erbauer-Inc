from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils.translation import get_language, override

from main.tasks import send_contact_email_task


class ContactEmailTaskTests(SimpleTestCase):
    def test_requested_language_is_used_and_previous_language_is_restored(self) -> None:
        data = {"name": "Visitor", "phone": "+16045550123", "message": "Question"}
        for language in ("en", "uk", None):
            with self.subTest(language=language), override("uk"):
                with patch("main.tasks.send_contact_email") as send:
                    send.side_effect = lambda payload: self.assertEqual(
                        get_language(), language
                    )
                    send_contact_email_task.run(data=data, language=language)
                    send.assert_called_once_with(data)
                self.assertEqual(get_language(), "uk")

    def test_delivery_failure_propagates_without_retry_or_language_leak(self) -> None:
        with override("en"), patch("main.tasks.send_contact_email") as send:
            send.side_effect = RuntimeError("test delivery failure")
            with patch.object(send_contact_email_task, "retry") as retry:
                with self.assertRaises(RuntimeError):
                    send_contact_email_task.run(data={}, language="uk")
                retry.assert_not_called()
            self.assertEqual(get_language(), "en")
            send.assert_called_once_with({})
