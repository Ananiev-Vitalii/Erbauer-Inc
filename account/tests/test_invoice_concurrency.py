from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier, Event
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import (
    OperationalError,
    close_old_connections,
    connection,
    connections,
    transaction,
)
from django.test import TransactionTestCase
from django.utils import timezone

from account.models import Employee, EmployeeSimpleInvoice, EmployeeWorkHours
from account.services.simple_invoice_period import reserve_work_hours_for_invoice
from account.services.simple_invoice_processing import expire_stale_simple_invoice
from account.services.simple_invoice_submission import submit_simple_invoice
from account.services.work_hours import save_employee_work_hours
from account.tasks import process_simple_invoice_task
from account.tests.helpers import (
    address_data,
    create_invoice,
    freeze_clock,
    invoice_data,
    mock_invoice_boundaries,
)
from user.tests.helpers import employee


@contextmanager
def thread_database() -> Iterator[int]:
    """Use a separate PostgreSQL connection with bounded database waits."""
    close_old_connections()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '3s'")
            cursor.execute("SET statement_timeout = '10s'")
            cursor.execute("SELECT pg_backend_pid()")
            pid = cursor.fetchone()[0]
        yield pid
    finally:
        connections.close_all()


class InvoiceConcurrencyTests(TransactionTestCase):
    def setUp(self) -> None:
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row locks are required.")
        freeze_clock(self)
        self.member = employee()
        self.invoice = create_invoice(self.member)
        self.day = timezone.localdate() - timedelta(days=1)
        self.hours = EmployeeWorkHours.objects.create(
            employee=self.member, work_date=self.day, hours=Decimal("7.50")
        )
        self.boundaries = mock_invoice_boundaries(self)

    def test_two_real_workers_claim_and_send_only_once(self) -> None:
        barrier = Barrier(2, timeout=10)

        def claim(*, invoice: EmployeeSimpleInvoice) -> int:
            barrier.wait()
            return reserve_work_hours_for_invoice(invoice=invoice)

        def worker() -> int:
            with thread_database() as pid:
                process_simple_invoice_task.run(self.invoice.pk, address_data())
                return pid

        with (
            patch("account.tasks.reserve_work_hours_for_invoice", side_effect=claim),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            futures = [pool.submit(worker) for _ in range(2)]
            pids = [future.result(timeout=15) for future in futures]

        self.assertEqual(len(set(pids)), 2)
        self.invoice.refresh_from_db()
        self.hours.refresh_from_db()
        self.assertEqual(self.invoice.status, EmployeeSimpleInvoice.Status.SENT)
        self.assertEqual(self.hours.invoice_id, self.invoice.pk)
        for stage in ("xlsx", "pdf", "upload", "email"):
            self.boundaries[stage].assert_called_once()

    def test_claim_requires_employee_lock_held_by_another_connection(self) -> None:
        def claim() -> str | None:
            with thread_database():
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '500ms'")
                try:
                    reserve_work_hours_for_invoice(invoice=self.invoice)
                except OperationalError as error:
                    cause = error.__cause__
                    return getattr(cause, "sqlstate", None) or getattr(
                        cause, "pgcode", None
                    )
                return None

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                Employee.objects.select_for_update().get(pk=self.member.pk)
                result = pool.submit(claim).result(timeout=15)
        self.assertEqual(result, "55P03")
        self.invoice.refresh_from_db()
        self.hours.refresh_from_db()
        self.assertEqual(self.invoice.status, EmployeeSimpleInvoice.Status.PROCESSING)
        self.assertIsNone(self.hours.invoice_id)

    def test_concurrent_edit_and_submission_preserve_hours_and_reservation(
        self,
    ) -> None:
        self.invoice.delete()
        barrier = Barrier(3, timeout=10)

        def submit() -> tuple[int, int]:
            with thread_database() as pid:
                barrier.wait()
                invoice = submit_simple_invoice(
                    employee=self.member,
                    invoice_data=invoice_data(),
                    employee_data=address_data(),
                )
                return pid, invoice.pk

        def edit() -> tuple[int, bool]:
            with thread_database() as pid:
                barrier.wait()
                try:
                    save_employee_work_hours(
                        employee=self.member, work_date=self.day, raw_hours="8.00"
                    )
                except ValidationError:
                    return pid, False
                return pid, True

        with ThreadPoolExecutor(max_workers=2) as pool:
            with transaction.atomic():
                Employee.objects.select_for_update().get(pk=self.member.pk)
                submit_future = pool.submit(submit)
                edit_future = pool.submit(edit)
                barrier.wait()
            submit_pid, invoice_id = submit_future.result(timeout=15)
            edit_pid, edited = edit_future.result(timeout=15)

        self.assertNotEqual(submit_pid, edit_pid)
        invoice = EmployeeSimpleInvoice.objects.get(pk=invoice_id)
        self.assertEqual(invoice.status, EmployeeSimpleInvoice.Status.PROCESSING)
        self.assertEqual(reserve_work_hours_for_invoice(invoice=invoice), 1)
        invoice.refresh_from_db()
        self.hours.refresh_from_db()
        self.assertEqual(invoice.status, EmployeeSimpleInvoice.Status.PREPARING)
        self.assertEqual(self.hours.invoice_id, invoice.pk)
        self.assertEqual(self.hours.hours, Decimal("8.00" if edited else "7.50"))
        self.boundaries["publish"].assert_called_once()
        with self.assertRaises(ValidationError):
            save_employee_work_hours(
                employee=self.member, work_date=self.day, raw_hours="0"
            )

    def test_cleanup_commits_while_worker_waits_for_email_and_worker_cannot_revert_it(
        self,
    ) -> None:
        entered_email = Event()
        release_email = Event()

        def send(*, invoice: EmployeeSimpleInvoice, pdf_path: Path) -> None:
            self.assertFalse(connection.in_atomic_block)
            entered_email.set()
            self.assertTrue(release_email.wait(timeout=10))

        def worker() -> None:
            with thread_database():
                process_simple_invoice_task.run(self.invoice.pk, address_data())

        self.boundaries["email"].side_effect = send
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker)
            try:
                self.assertTrue(entered_email.wait(timeout=10))
                later = timezone.now() + timedelta(minutes=6)
                with patch("django.utils.timezone.now", return_value=later):
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            cursor.execute("SET LOCAL lock_timeout = '3s'")
                            cursor.execute("SET LOCAL statement_timeout = '8s'")
                        self.assertTrue(expire_stale_simple_invoice(
                            invoice_id=self.invoice.pk
                        ))
                    release_email.set()
                    future.result(timeout=15)
            finally:
                release_email.set()
        self.invoice.refresh_from_db()
        self.hours.refresh_from_db()
        self.assertEqual(self.invoice.status, EmployeeSimpleInvoice.Status.FAILED)
        self.assertIsNone(self.hours.invoice_id)
