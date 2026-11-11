from unittest.mock import patch

from django.db import transaction
from django.test import TestCase

from account.models import EmployeeSimpleInvoice
from account.services.simple_invoice_submission import submit_simple_invoice
from account.tests.helpers import address_data, freeze_clock, invoice_data
from user.tests.helpers import employee


class InvoiceSubmissionTests(TestCase):
    def setUp(self) -> None:
        freeze_clock(self)
        self.member = employee()

    def test_creation_defers_publication_until_commit(self) -> None:
        with patch(
            "account.services.simple_invoice_submission."
            "process_simple_invoice_task.apply_async"
        ) as publish:
            with self.captureOnCommitCallbacks(execute=True):
                invoice = submit_simple_invoice(
                    employee=self.member,
                    invoice_data=invoice_data(),
                    employee_data=address_data(),
                )
                invoice.refresh_from_db()
                self.assertEqual(
                    invoice.status, EmployeeSimpleInvoice.Status.PROCESSING
                )
                publish.assert_not_called()
            publish.assert_called_once_with(
                args=(invoice.pk, address_data()), expires=300
            )

    def test_rollback_discards_invoice_and_publication(self) -> None:
        with patch(
            "account.services.simple_invoice_submission."
            "process_simple_invoice_task.apply_async"
        ) as publish:
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(RuntimeError), transaction.atomic():
                    submit_simple_invoice(
                        employee=self.member,
                        invoice_data=invoice_data(),
                        employee_data=address_data(),
                    )
                    raise RuntimeError("Abort submission")
            publish.assert_not_called()
        self.assertFalse(EmployeeSimpleInvoice.objects.exists())
