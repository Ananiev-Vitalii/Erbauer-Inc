from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase
from django.utils import timezone
from openpyxl import load_workbook

from account.models import Employee, EmployeeSimpleInvoice
from account.services.simple_invoice_xlsx import generate_simple_invoice_xlsx
from account.tests.helpers import invoice_data


class InvoiceXlsxRegressionTests(SimpleTestCase):
    def test_untrusted_text_stays_text_and_financial_formulas_stay_formulas(
        self,
    ) -> None:
        invoice = EmployeeSimpleInvoice(
            employee=Employee(first_name_en="Test", last_name_en="=1+1"),
            created_at=timezone.now(),
            **{**invoice_data(), "gst_account_number": "=4+4"},
        )
        data = {
            "street_address": "=1+1", "city": "=2+2", "province": "BC",
            "postal_code": "=3+3",
        }
        with TemporaryDirectory() as directory:
            path = generate_simple_invoice_xlsx(
                invoice=invoice,
                employee_data=data,
                output_path=Path(directory) / "i.xlsx",
            )
            workbook = load_workbook(path, data_only=False)
            try:
                sheet = workbook["Invoice"]
                expected_text = {
                    "C6": "=1+1 Test", "C7": "=1+1", "C8": "=2+2, BC",
                    "C9": "=3+3", "C10": "=4+4",
                }
                for cell, value in expected_text.items():
                    self.assertEqual(sheet[cell].value, value)
                    self.assertEqual(sheet[cell].data_type, "s")
                for row in range(13, 26):
                    self.assertEqual(sheet[f"G{row}"].value, f"=E{row}*F{row}")
                    self.assertEqual(sheet[f"G{row}"].data_type, "f")
                for cell, formula in {
                    "G26": "=SUM(G13:G25)", "G27": "=G26*5.00%",
                    "G28": "=G26*2.00%", "G29": "=G26+G27-G28",
                }.items():
                    self.assertEqual(sheet[cell].value, formula)
                    self.assertEqual(sheet[cell].data_type, "f")
                self.assertEqual(sheet["E14"].data_type, "n")
                self.assertEqual(sheet["F14"].data_type, "n")
                self.assertEqual(Decimal(str(sheet["E14"].value)), invoice.hours)
                self.assertEqual(Decimal(str(sheet["F14"].value)), invoice.rate)
            finally:
                workbook.close()
