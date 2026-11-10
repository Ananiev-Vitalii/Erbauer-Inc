import logging
import sys

from django.conf import settings
from django.test import SimpleTestCase

from config.logging import EmailErrorFormatter


class EmailLoggingTests(SimpleTestCase):
    def test_exception_details_and_chained_secrets_are_redacted(self) -> None:
        try:
            try:
                raise ValueError("secret-token-and-url")
            except ValueError as cause:
                raise RuntimeError("secret-provider-payload") from cause
        except RuntimeError:
            record = logging.LogRecord("user.services.email", logging.ERROR,
                                       __file__, 1, "Email failed", (), sys.exc_info())
        output = EmailErrorFormatter().format(record)
        self.assertIn("RuntimeError", output)
        self.assertIn("Traceback", output)
        self.assertNotIn("secret-token-and-url", output)
        self.assertNotIn("secret-provider-payload", output)

    def test_both_email_loggers_have_unfiltered_stderr_handler(self) -> None:
        handler = settings.LOGGING["handlers"]["auth_email_console"]
        self.assertEqual(handler["stream"], "ext://sys.stderr")
        self.assertFalse(handler.get("filters"))
        for name in ("user.services.email", "django.contrib.auth"):
            config = settings.LOGGING["loggers"][name]
            self.assertIn("auth_email_console", config["handlers"])
            self.assertFalse(config["propagate"])
