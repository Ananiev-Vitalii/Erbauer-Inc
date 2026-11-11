from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from account.models import EmployeeSimpleInvoice, EmployeeWorkHours
from account.services.simple_invoice_period import reserve_work_hours_for_invoice
from account.services.work_hours import (
    get_employee_month_total,
    save_employee_work_hours,
)
from account.tests.helpers import create_invoice, freeze_clock
from user.tests.helpers import employee


class WorkHoursInvoiceRulesTests(TestCase):
    def setUp(self) -> None:
        freeze_clock(self)
        self.member = employee()
        self.day = timezone.localdate() - timedelta(days=1)

    def test_active_and_sent_periods_block_creating_updating_and_deleting_hours(
        self,
    ) -> None:
        for status in (
            EmployeeSimpleInvoice.Status.PROCESSING,
            EmployeeSimpleInvoice.Status.PREPARING,
            EmployeeSimpleInvoice.Status.SENT,
        ):
            with self.subTest(status=status):
                invoice = create_invoice(self.member, status)
                with self.assertRaises(ValidationError):
                    save_employee_work_hours(
                        employee=self.member, work_date=self.day, raw_hours="8.00"
                    )
                entry = EmployeeWorkHours.objects.create(
                    employee=self.member, work_date=self.day, hours=Decimal("7.50")
                )
                for value in ("8.00", "0"):
                    with self.assertRaises(ValidationError):
                        save_employee_work_hours(
                            employee=self.member, work_date=self.day, raw_hours=value
                        )
                entry.refresh_from_db()
                self.assertEqual(entry.hours, Decimal("7.50"))
                entry.delete()
                invoice.delete()

        create_invoice(self.member, EmployeeSimpleInvoice.Status.FAILED)
        entry = save_employee_work_hours(
            employee=self.member, work_date=self.day, raw_hours="8.00"
        )
        self.assertEqual(entry.hours, Decimal("8.00"))
        save_employee_work_hours(
            employee=self.member, work_date=self.day, raw_hours="0"
        )
        self.assertFalse(EmployeeWorkHours.objects.exists())

    def test_manual_invoice_hours_replace_totals_without_changing_calendar_entries(
        self,
    ) -> None:
        entry = EmployeeWorkHours.objects.create(
            employee=self.member, work_date=self.day, hours=Decimal("7.50")
        )
        invoice = create_invoice(self.member)
        self.assertEqual(reserve_work_hours_for_invoice(invoice=invoice), 1)
        entry.refresh_from_db()
        self.assertEqual(entry.hours, Decimal("7.50"))
        self.assertEqual(entry.invoice_id, invoice.pk)
        self.assertEqual(invoice.hours, Decimal("12.00"))
        self.assertEqual(
            get_employee_month_total(
                employee=self.member, year=self.day.year, month=self.day.month
            ),
            Decimal("12.00"),
        )
