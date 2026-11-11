from __future__ import annotations

import copy
import io
import logging
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import TracebackType
from unittest.mock import patch

from django.test import SimpleTestCase

from account.services.simple_invoice_pdf import (
    SimpleInvoicePdfConversionError,
    convert_xlsx_to_pdf,
)


def sensitive_exception_info(
) -> tuple[type[BaseException], BaseException, TracebackType | None]:
    try:
        try:
            raise ValueError("sensitive-token-placeholder")
        except ValueError as cause:
            raise RuntimeError("recipient@example.invalid provider-payload") from cause
    except RuntimeError:
        return sys.exc_info()


class AccountLoggingTests(SimpleTestCase):
    def test_configured_account_handler_redacts_provider_and_chained_messages(
        self,
    ) -> None:
        handler = next(
            handler for handler in logging.getLogger("account").handlers
            if handler.name == "account_console"
        )
        stream = io.StringIO()
        with patch.object(handler, "stream", stream):
            logging.getLogger("account.services.simple_invoice_service").error(
                "Invoice upload failed. Invoice id: 42",
                exc_info=sensitive_exception_info(),
            )
        output = stream.getvalue()
        self.assertIn("Invoice id: 42", output)
        self.assertIn("RuntimeError", output)
        self.assertIn("sensitive_exception_info", output)
        self.assertNotIn("recipient@example.invalid", output)
        self.assertNotIn("provider-payload", output)
        self.assertNotIn("sensitive-token-placeholder", output)

    def test_celery_record_redacts_all_sensitive_fields_and_preserves_other_tasks(
        self,
    ) -> None:
        data = {
            "name": "account.tasks.process_simple_invoice_task",
            "id": "isolated-task-id",
            "args": "(42, {'street_address': 'sensitive-address'})",
            "kwargs": "{'token': 'sensitive-token-placeholder'}",
            "exc": "recipient@example.invalid provider-payload",
            "traceback": "sensitive-raw-traceback",
        }
        record = logging.LogRecord(
            "celery.app.trace", logging.ERROR, __file__, 1,
            "Task %(name)s failed: %(exc)s", (data,), sensitive_exception_info(),
        )
        record.data = data
        other = copy.copy(record)
        other.data = {**data, "name": "main.tasks.send_contact_email_task"}
        other.args = other.data
        original_args = other.args
        original_exception = other.exc_info
        filters = logging.getLogger("celery.app.trace").filters
        self.assertTrue(filters)
        for filter_instance in filters:
            self.assertTrue(filter_instance.filter(record))
            self.assertTrue(filter_instance.filter(other))
        output = logging.Formatter("%(message)s").format(record)
        combined = output + repr(record.data) + repr(record.args)
        for sensitive in (
            "recipient@example.invalid", "provider-payload", "sensitive-address",
            "sensitive-token-placeholder", "sensitive-raw-traceback",
        ):
            self.assertNotIn(sensitive, combined)
        self.assertIn("Invoice id: 42", output)
        self.assertIn("RuntimeError", output)
        self.assertIn("ValueError", output)
        self.assertIsNone(record.exc_info)
        self.assertIs(other.args, original_args)
        self.assertIs(other.exc_info, original_exception)

    def test_django_cleanup_record_does_not_expose_file_or_provider_payload(
        self,
    ) -> None:
        record = logging.LogRecord(
            "django_cleanup.handlers", logging.ERROR, __file__, 1,
            "Deletion failed: %s %s %s %s",
            ("sensitive-file-path", "account", "profile", "avatar"),
            sensitive_exception_info(),
        )
        filters = logging.getLogger("django_cleanup.handlers").filters
        self.assertTrue(filters)
        for filter_instance in filters:
            self.assertTrue(filter_instance.filter(record))
        output = logging.Formatter("%(message)s").format(record)
        self.assertIn("account.profile", output)
        self.assertIn("RuntimeError", output)
        for sensitive in (
            "sensitive-file-path", "provider-payload", "recipient@example.invalid",
            "sensitive-token-placeholder",
        ):
            self.assertNotIn(sensitive, output)

    def test_libreoffice_error_keeps_exit_code_without_raw_process_output(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=7, stdout="sensitive-stdout", stderr="sensitive-stderr"
        )
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with patch(
                "account.services.simple_invoice_pdf.subprocess.run",
                return_value=completed,
            ):
                with self.assertRaises(SimpleInvoicePdfConversionError) as caught:
                    convert_xlsx_to_pdf(
                        xlsx_path=root / "invoice.xlsx", output_dir=root
                    )
        self.assertEqual(caught.exception.returncode, 7)
        self.assertNotIn("sensitive-stdout", str(caught.exception))
        self.assertNotIn("sensitive-stderr", str(caught.exception))
        data = {
            "name": "account.tasks.process_simple_invoice_task", "id": "conversion",
            "args": "(42, {})",
        }
        record = logging.LogRecord(
            "celery.app.trace", logging.ERROR, __file__, 1, "Failure", (),
            (type(caught.exception), caught.exception, caught.exception.__traceback__),
        )
        record.data = data
        for filter_instance in logging.getLogger("celery.app.trace").filters:
            filter_instance.filter(record)
        self.assertIn("Exit code: 7", logging.Formatter("%(message)s").format(record))
