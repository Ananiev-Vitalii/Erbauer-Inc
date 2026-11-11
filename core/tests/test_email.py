from unittest.mock import patch

from django.core import mail
from django.test import SimpleTestCase, override_settings
from django.utils.translation import gettext_lazy, override

from core.services.email import (
    EmailAttachment,
    EmailDeliveryError,
    EmailPayload,
    send_html_email,
)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class HtmlEmailServiceTests(SimpleTestCase):
    def setUp(self) -> None:
        self.enterContext(patch("django.core.mail.message.DNS_NAME", "tests.invalid"))
        self.render = self.enterContext(
            patch("core.services.email.render_to_string", return_value="email body")
        )

    def payload(self) -> EmailPayload:
        return EmailPayload(
            subject="Test email",
            template_name="test-email.html",
            context={"value": 1},
            to=["recipient@example.invalid"],
        )

    def test_empty_effective_recipients_raise_without_sending(self) -> None:
        for recipients in ([], [""], [None]):
            with self.subTest(recipients=recipients):
                payload = self.payload()
                payload.to = recipients
                payload.reply_to = ["reply@example.invalid"]
                with patch("core.services.email.EmailMessage.send") as send:
                    with self.assertRaises(EmailDeliveryError):
                        send_html_email(payload)
                send.assert_not_called()

    def test_unsuccessful_backend_result_raises_without_retry(self) -> None:
        for result in (0, 2, None):
            with self.subTest(result=result):
                with patch(
                    "core.services.email.EmailMessage.send", return_value=result
                ) as send:
                    with self.assertRaises(EmailDeliveryError):
                        send_html_email(self.payload())
                send.assert_called_once_with()

    def test_backend_exception_propagates_unchanged(self) -> None:
        error = ConnectionError("Synthetic email backend failure")
        with patch("core.services.email.EmailMessage.send", side_effect=error):
            with self.assertRaises(ConnectionError) as raised:
                send_html_email(self.payload())
        self.assertIs(raised.exception, error)

    def test_success_preserves_message_fields_and_pdf_attachment(self) -> None:
        payload = self.payload()
        payload.cc = ["copy@example.invalid"]
        payload.bcc = ["hidden@example.invalid"]
        payload.reply_to = ["reply@example.invalid"]
        payload.attachments = [
            EmailAttachment("invoice.pdf", b"test PDF bytes", "application/pdf")
        ]

        self.assertIsNone(send_html_email(payload))

        self.render.assert_called_once_with(
            payload.template_name, context=payload.context
        )
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.subject, payload.subject)
        self.assertEqual(message.to, payload.to)
        self.assertEqual(message.cc, payload.cc)
        self.assertEqual(message.bcc, payload.bcc)
        self.assertEqual(message.reply_to, payload.reply_to)
        self.assertEqual(message.content_subtype, "html")
        self.assertEqual(message.attachments[0].filename, "invoice.pdf")
        self.assertEqual(message.attachments[0].content, b"test PDF bytes")
        self.assertEqual(message.attachments[0].mimetype, "application/pdf")

    def test_cc_or_bcc_alone_is_a_valid_recipient(self) -> None:
        for field in ("cc", "bcc"):
            with self.subTest(field=field):
                payload = self.payload()
                payload.to = []
                setattr(payload, field, ["recipient@example.invalid"])
                self.assertIsNone(send_html_email(payload))
                self.assertEqual(
                    mail.outbox[-1].recipients(), ["recipient@example.invalid"]
                )

    def test_lazy_subject_can_be_serialized(self) -> None:
        payload = self.payload()
        payload.subject = gettext_lazy(payload.subject)
        with override("uk"):
            self.assertIsNone(send_html_email(payload))
            self.assertEqual(mail.outbox[0].message()["Subject"], str(payload.subject))
