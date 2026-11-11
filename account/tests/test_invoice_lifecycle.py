from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.files import File
from django.db import OperationalError, connection, transaction
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from kombu.exceptions import OperationalError as BrokerError

from account.models import EmployeeSimpleInvoice, EmployeeWorkHours
from account.services.simple_invoice_period import (
    is_work_date_locked,
    reserve_work_hours_for_invoice,
)
from account.services.simple_invoice_processing import (
    SimpleInvoiceProcessingCancelled,
    expire_stale_simple_invoice,
    is_simple_invoice_processing_expired,
    mark_simple_invoice_sent,
)
from account.services.simple_invoice_submission import submit_simple_invoice
from account.tasks import process_simple_invoice_task
from account.tests.helpers import (
    address_data,
    create_invoice,
    freeze_clock,
    invoice_data,
    mock_invoice_boundaries,
    save_pdf,
    write_pdf,
    write_xlsx,
)
from account.types import EmployeeAddressData
from user.models import User
from user.tests.helpers import employee


class InvoiceLifecycleTests(TransactionTestCase):
    def setUp(self) -> None:
        freeze_clock(self)
        self.member = employee()
        self.boundaries = mock_invoice_boundaries(self)
        self.day = timezone.localdate() - timedelta(days=1)
        self.hours = EmployeeWorkHours.objects.create(
            employee=self.member, work_date=self.day, hours=Decimal("7.50")
        )

    def test_success_commits_claim_and_runs_external_operations_without_locks(
        self,
    ) -> None:
        invoice = submit_simple_invoice(
            employee=self.member,
            invoice_data=invoice_data(),
            employee_data=address_data(),
        )
        self.assertEqual(invoice.status, EmployeeSimpleInvoice.Status.PROCESSING)

        def assert_claim() -> None:
            self.assertFalse(connection.in_atomic_block)
            current = EmployeeSimpleInvoice.objects.get(pk=invoice.pk)
            self.assertEqual(current.status, EmployeeSimpleInvoice.Status.PREPARING)
            self.hours.refresh_from_db()
            self.assertEqual(self.hours.invoice_id, invoice.pk)

        def generate(
            *,
            invoice: EmployeeSimpleInvoice,
            employee_data: EmployeeAddressData,
            output_path: Path,
        ) -> Path:
            assert_claim()
            return write_xlsx(
                invoice=invoice, employee_data=employee_data, output_path=output_path
            )

        def convert(*, xlsx_path: Path, output_dir: Path) -> Path:
            assert_claim()
            return write_pdf(xlsx_path=xlsx_path, output_dir=output_dir)

        def upload(name: str, content: File, max_length: int | None = None) -> str:
            assert_claim()
            return save_pdf(name, content, max_length)

        def send(*, invoice: EmployeeSimpleInvoice, pdf_path: Path) -> None:
            assert_claim()
            self.assertTrue(pdf_path.is_file())

        self.boundaries["xlsx"].side_effect = generate
        self.boundaries["pdf"].side_effect = convert
        self.boundaries["upload"].side_effect = upload
        self.boundaries["email"].side_effect = send
        process_simple_invoice_task.run(invoice.pk, address_data())

        invoice.refresh_from_db()
        self.hours.refresh_from_db()
        self.assertEqual(invoice.status, EmployeeSimpleInvoice.Status.SENT)
        self.assertEqual(
            invoice.pdf_file.name, self.boundaries["upload"].call_args.args[0]
        )
        self.assertEqual(self.hours.hours, Decimal("7.50"))
        self.assertEqual(self.hours.invoice_id, invoice.pk)
        self.assertTrue(is_work_date_locked(employee=self.member, work_date=self.day))
        self.boundaries["email"].assert_called_once()
        process_simple_invoice_task.run(invoice.pk, address_data())
        self.boundaries["email"].assert_called_once()
        self.boundaries["delete"].assert_not_called()

    def test_preparation_upload_and_email_failures_release_hours_for_resubmission(
        self,
    ) -> None:
        for stage in ("xlsx", "pdf", "upload", "email"):
            with self.subTest(stage=stage):
                invoice = create_invoice(self.member)
                boundary = self.boundaries[stage]
                original = boundary.side_effect
                boundary.side_effect = RuntimeError("Stage failed")
                try:
                    with self.assertRaises(RuntimeError):
                        process_simple_invoice_task.run(invoice.pk, address_data())
                finally:
                    boundary.side_effect = original
                invoice.refresh_from_db()
                self.hours.refresh_from_db()
                self.assertEqual(invoice.status, EmployeeSimpleInvoice.Status.FAILED)
                self.assertIsNone(self.hours.invoice_id)
                self.assertFalse(is_work_date_locked(
                    employee=self.member, work_date=self.day
                ))
        replacement = submit_simple_invoice(
            employee=self.member,
            invoice_data=invoice_data(),
            employee_data=address_data(),
        )
        self.assertEqual(replacement.status, EmployeeSimpleInvoice.Status.PROCESSING)

    def test_claim_and_reservation_roll_back_together(self) -> None:
        invoice = create_invoice(self.member)
        with self.assertRaises(RuntimeError), transaction.atomic():
            reserve_work_hours_for_invoice(invoice=invoice)
            raise RuntimeError("Abort claim")
        invoice.refresh_from_db()
        self.hours.refresh_from_db()
        self.assertEqual(invoice.status, EmployeeSimpleInvoice.Status.PROCESSING)
        self.assertIsNone(self.hours.invoice_id)

    def test_both_active_states_expire_at_five_minutes_from_creation(self) -> None:
        now = timezone.now()
        for status in (
            EmployeeSimpleInvoice.Status.PROCESSING,
            EmployeeSimpleInvoice.Status.PREPARING,
        ):
            with self.subTest(status=status):
                invoice = create_invoice(self.member)
                if status == EmployeeSimpleInvoice.Status.PREPARING:
                    reserve_work_hours_for_invoice(invoice=invoice)
                with patch(
                    "account.services.simple_invoice_processing.timezone.now",
                    return_value=now,
                ):
                    created_at = now - timedelta(minutes=5) + timedelta(microseconds=1)
                    EmployeeSimpleInvoice.objects.filter(pk=invoice.pk).update(
                        created_at=created_at
                    )
                    invoice.refresh_from_db()
                    self.assertFalse(is_simple_invoice_processing_expired(invoice))
                    EmployeeSimpleInvoice.objects.filter(pk=invoice.pk).update(
                        created_at=now - timedelta(minutes=5)
                    )
                    self.assertTrue(expire_stale_simple_invoice(invoice_id=invoice.pk))
                invoice.refresh_from_db()
                self.hours.refresh_from_db()
                self.assertEqual(invoice.status, EmployeeSimpleInvoice.Status.FAILED)
                self.assertIsNone(self.hours.invoice_id)

    def test_late_worker_cannot_finalize_failed_invoice_or_touch_new_reservation(
        self,
    ) -> None:
        old = create_invoice(self.member)
        reserve_work_hours_for_invoice(invoice=old)
        EmployeeSimpleInvoice.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(minutes=6)
        )
        expire_stale_simple_invoice(invoice_id=old.pk)
        replacement = create_invoice(self.member)
        reserve_work_hours_for_invoice(invoice=replacement)
        with self.assertRaises(SimpleInvoiceProcessingCancelled):
            mark_simple_invoice_sent(
                invoice_id=old.pk, employee_id=self.member.pk, pdf_name="late.pdf"
            )
        process_simple_invoice_task.run(old.pk, address_data())
        self.hours.refresh_from_db()
        old.refresh_from_db()
        self.assertEqual(old.status, EmployeeSimpleInvoice.Status.FAILED)
        self.assertEqual(self.hours.invoice_id, replacement.pk)
        self.assertEqual(self.hours.hours, Decimal("7.50"))
        self.boundaries["email"].assert_not_called()
        self.boundaries["xlsx"].assert_not_called()

    def test_expiry_during_generation_prevents_email(self) -> None:
        invoice = create_invoice(self.member)

        def generate(
            *,
            invoice: EmployeeSimpleInvoice,
            employee_data: EmployeeAddressData,
            output_path: Path,
        ) -> Path:
            result = write_xlsx(
                invoice=invoice, employee_data=employee_data, output_path=output_path
            )
            EmployeeSimpleInvoice.objects.filter(pk=invoice.pk).update(
                created_at=timezone.now() - timedelta(minutes=6)
            )
            expire_stale_simple_invoice(invoice_id=invoice.pk)
            return result

        self.boundaries["xlsx"].side_effect = generate
        process_simple_invoice_task.run(invoice.pk, address_data())
        invoice.refresh_from_db()
        self.hours.refresh_from_db()
        self.assertEqual(invoice.status, EmployeeSimpleInvoice.Status.FAILED)
        self.assertIsNone(self.hours.invoice_id)
        self.boundaries["email"].assert_not_called()
        self.boundaries["delete"].assert_called_once()

    def test_expiry_during_email_does_not_relock_replacement_hours(self) -> None:
        invoice = create_invoice(self.member)
        replacements = []

        def send(*, invoice: EmployeeSimpleInvoice, pdf_path: Path) -> None:
            self.assertFalse(connection.in_atomic_block)
            EmployeeSimpleInvoice.objects.filter(pk=invoice.pk).update(
                created_at=timezone.now() - timedelta(minutes=6)
            )
            expire_stale_simple_invoice(invoice_id=invoice.pk)
            replacement = create_invoice(self.member)
            reserve_work_hours_for_invoice(invoice=replacement)
            replacements.append(replacement.pk)

        self.boundaries["email"].side_effect = send
        process_simple_invoice_task.run(invoice.pk, address_data())
        invoice.refresh_from_db()
        self.hours.refresh_from_db()
        self.assertEqual(invoice.status, EmployeeSimpleInvoice.Status.FAILED)
        self.assertEqual(self.hours.invoice_id, replacements[0])
        self.assertEqual(self.hours.hours, Decimal("7.50"))

    def test_lost_commit_confirmation_keeps_persisted_sent_pdf(self) -> None:
        invoice = create_invoice(self.member)

        def finalize(*, invoice_id: int, employee_id: int, pdf_name: str) -> None:
            mark_simple_invoice_sent(
                invoice_id=invoice_id, employee_id=employee_id, pdf_name=pdf_name
            )
            raise OperationalError("Simulated lost commit confirmation")

        with patch(
            "account.services.simple_invoice_service.mark_simple_invoice_sent",
            side_effect=finalize,
        ):
            with self.assertRaises(OperationalError):
                process_simple_invoice_task.run(invoice.pk, address_data())
        invoice.refresh_from_db()
        self.hours.refresh_from_db()
        self.assertEqual(invoice.status, EmployeeSimpleInvoice.Status.SENT)
        self.assertTrue(invoice.pdf_file.name)
        self.assertEqual(self.hours.invoice_id, invoice.pk)
        self.boundaries["delete"].assert_not_called()

    def test_broker_failure_returns_bound_form_and_committed_failed_invoice(
        self,
    ) -> None:
        user = User.objects.create_user(
            email=self.member.email, is_active=True, is_verified=True
        )
        self.member.user = user
        self.member.save(update_fields=["user"])
        self.client.force_login(user)
        self.boundaries["publish"].side_effect = BrokerError("Broker unavailable")
        response = self.client.post(
            reverse("account:simple_invoice_create"),
            {**invoice_data(), **address_data()},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["invoice_form"]
        self.assertTrue(form.is_bound)
        self.assertIn("__all__", form.errors)
        self.assertEqual(form.data["hours"], "12.00")
        self.assertEqual(form.data["street_address"], address_data()["street_address"])
        self.assertEqual(
            EmployeeSimpleInvoice.objects.get().status,
            EmployeeSimpleInvoice.Status.FAILED,
        )

    def test_ambiguous_publish_failure_does_not_cancel_claimed_invoice(self) -> None:
        def publish(*, args: tuple[int, EmployeeAddressData], expires: int) -> None:
            invoice = EmployeeSimpleInvoice.objects.get(pk=args[0])
            reserve_work_hours_for_invoice(invoice=invoice)
            raise BrokerError("Simulated lost publication confirmation")

        self.boundaries["publish"].side_effect = publish
        invoice = submit_simple_invoice(
            employee=self.member,
            invoice_data=invoice_data(),
            employee_data=address_data(),
        )
        invoice.refresh_from_db()
        self.hours.refresh_from_db()
        self.assertEqual(invoice.status, EmployeeSimpleInvoice.Status.PREPARING)
        self.assertEqual(self.hours.invoice_id, invoice.pk)
