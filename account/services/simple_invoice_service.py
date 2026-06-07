from pathlib import Path
import tempfile

from account.services.simple_invoice_xlsx import generate_simple_invoice_xlsx
from account.services.simple_invoice_pdf import convert_xlsx_to_pdf
from account.services.simple_invoice_email import send_simple_invoice_email


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