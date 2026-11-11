from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from django.core.files import File
from django.core.files.storage import Storage
from django.db import DatabaseError, transaction

from account.models import EmployeeSimpleInvoice
from account.services.simple_invoice_email import send_simple_invoice_email
from account.services.simple_invoice_pdf import convert_xlsx_to_pdf
from account.services.simple_invoice_processing import (
    check_preparing_simple_invoice,
    lock_simple_invoice,
    mark_simple_invoice_sent,
)
from account.services.simple_invoice_xlsx import generate_simple_invoice_xlsx
from account.types import EmployeeAddressData

logger = logging.getLogger(__name__)


def _delete_uploaded_pdf(
    *,
    storage: Storage,
    pdf_name: str | None,
    invoice_id: int,
    employee_id: int,
) -> None:
    """Keep the file when a persisted reference or database uncertainty remains."""
    if not pdf_name:
        return

    try:
        with transaction.atomic():
            invoice = lock_simple_invoice(
                invoice_id=invoice_id,
                employee_id=employee_id,
            )
            if invoice is not None and invoice.pdf_file.name == pdf_name:
                return
    except DatabaseError as error:
        logger.error(
            "Skipped invoice PDF deletion: database state is unknown (%s). "
            "Invoice id: %s",
            type(error).__name__,
            invoice_id,
        )
        return

    try:
        storage.delete(pdf_name)
    except Exception as error:
        logger.exception(
            "Failed to delete uploaded invoice PDF (%s). Invoice id: %s",
            type(error).__name__,
            invoice_id,
        )


def process_simple_invoice(
    *,
    invoice: EmployeeSimpleInvoice,
    employee_data: EmployeeAddressData,
) -> None:
    """Prepare and send outside locks, then finalize the current worker claim."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        xlsx_path = temp_path / f"simple-invoice-IA ({invoice.invoice_number}).xlsx"

        generate_simple_invoice_xlsx(
            invoice=invoice,
            employee_data=employee_data,
            output_path=xlsx_path,
        )

        pdf_path = convert_xlsx_to_pdf(xlsx_path=xlsx_path, output_dir=temp_path)

        uploaded_pdf_name = None
        storage = EmployeeSimpleInvoice._meta.get_field("pdf_file").storage

        try:
            with pdf_path.open("rb") as pdf:
                invoice.pdf_file.save(pdf_path.name, File(pdf), save=False)
            uploaded_pdf_name = invoice.pdf_file.name

            current_invoice = check_preparing_simple_invoice(
                invoice_id=invoice.pk,
                employee_id=invoice.employee_id,
            )
            send_simple_invoice_email(invoice=current_invoice, pdf_path=pdf_path)
            mark_simple_invoice_sent(
                invoice_id=invoice.pk,
                employee_id=invoice.employee_id,
                pdf_name=uploaded_pdf_name,
            )

        except Exception:
            _delete_uploaded_pdf(
                storage=storage,
                pdf_name=uploaded_pdf_name,
                invoice_id=invoice.pk,
                employee_id=invoice.employee_id,
            )

            raise
