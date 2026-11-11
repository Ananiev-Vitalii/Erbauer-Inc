from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.files import File
from django.test import SimpleTestCase
from django.utils import timezone

from account.models import Employee, EmployeeSimpleInvoice
from account.types import EmployeeAddressData, InvoiceData


def freeze_clock(test: SimpleTestCase) -> None:
    """Keep date windows stable even when a test runs across local midnight."""
    test.enterContext(patch("django.utils.timezone.now", return_value=timezone.now()))


def invoice_data() -> InvoiceData:
    day = timezone.localdate() - timedelta(days=1)
    return {
        "invoice_number": 1,
        "invoice_year": day.year,
        "invoice_month": day.month,
        "start_day": day.day,
        "end_day": day.day,
        "hours": Decimal("12.00"),
        "rate": Decimal("30.00"),
        "gst_account_number": "",
        "gst": Decimal("5.00"),
        "wsbc": Decimal("2.00"),
    }


def address_data() -> EmployeeAddressData:
    return {
        "street_address": "1 Test Street",
        "city": "Victoria",
        "province": "BC",
        "postal_code": "V8M 0B6",
    }


def create_invoice(
    member: Employee,
    status: str = EmployeeSimpleInvoice.Status.PROCESSING,
) -> EmployeeSimpleInvoice:
    return EmployeeSimpleInvoice.objects.create(
        employee=member, status=status, **invoice_data()
    )


def write_xlsx(
    *,
    invoice: EmployeeSimpleInvoice,
    employee_data: EmployeeAddressData,
    output_path: Path,
) -> Path:
    output_path.write_bytes(b"isolated-xlsx")
    return output_path


def write_pdf(*, xlsx_path: Path, output_dir: Path) -> Path:
    result = output_dir / f"{xlsx_path.stem}.pdf"
    result.write_bytes(b"%PDF-isolated-test")
    return result


def save_pdf(name: str, content: File, max_length: int | None = None) -> str:
    return name


def mock_invoice_boundaries(test: SimpleTestCase) -> dict[str, Mock]:
    """Replace external operations while keeping the ORM and transactions real."""
    storage = EmployeeSimpleInvoice._meta.get_field("pdf_file").storage
    return {
        "xlsx": test.enterContext(patch(
            "account.services.simple_invoice_service.generate_simple_invoice_xlsx",
            side_effect=write_xlsx,
        )),
        "pdf": test.enterContext(patch(
            "account.services.simple_invoice_service.convert_xlsx_to_pdf",
            side_effect=write_pdf,
        )),
        "upload": test.enterContext(
            patch.object(storage, "save", side_effect=save_pdf)
        ),
        "delete": test.enterContext(patch.object(storage, "delete", return_value=True)),
        "email": test.enterContext(patch(
            "account.services.simple_invoice_service.send_simple_invoice_email"
        )),
        "publish": test.enterContext(patch(
            "account.services.simple_invoice_submission."
            "process_simple_invoice_task.apply_async"
        )),
    }
