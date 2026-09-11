from pathlib import Path
import logging
import tempfile

from django.db import close_old_connections

from account.models import EmployeeSimpleInvoice
from account.services.simple_invoice_xlsx import generate_simple_invoice_xlsx
from account.services.simple_invoice_pdf import convert_xlsx_to_pdf
from account.services.simple_invoice_email import send_simple_invoice_email


logger = logging.getLogger(__name__)


def process_simple_invoice(*, invoice, employee_data):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        xlsx_path = temp_path / f"simple-invoice-IA ({invoice.invoice_number}).xlsx"

        generate_simple_invoice_xlsx(
            invoice=invoice,
            employee_data=employee_data,
            output_path=xlsx_path,
        )

        pdf_path = convert_xlsx_to_pdf(
            xlsx_path=xlsx_path,
            output_dir=temp_path,
        )

        send_simple_invoice_email(
            invoice=invoice,
            pdf_path=pdf_path,
        )


def process_simple_invoice_in_background(*, invoice_id, employee_data):
    try:
        close_old_connections()

        invoice = (
            EmployeeSimpleInvoice.objects
            .select_related("employee")
            .get(id=invoice_id)
        )

        process_simple_invoice(
            invoice=invoice,
            employee_data=employee_data,
        )

    except Exception:
        logger.exception(
            "Failed to process simple invoice in background. Invoice id: %s",
            invoice_id,
        )

    finally:
        close_old_connections()