import logging
from pathlib import Path
import tempfile

from django.core.files import File
from django.db import transaction

from account.models import (
    EmployeeSimpleInvoice,
    EmployeeWorkHours,
)
from account.services.simple_invoice_email import (
    send_simple_invoice_email,
)
from account.services.simple_invoice_pdf import (
    convert_xlsx_to_pdf,
)
from account.services.simple_invoice_processing import (
    SimpleInvoiceProcessingCancelled,
    SimpleInvoiceProcessingExpired,
    is_simple_invoice_processing_expired,
)
from account.services.simple_invoice_xlsx import (
    generate_simple_invoice_xlsx,
)

logger = logging.getLogger(__name__)


def _delete_uploaded_pdf(
    *,
    storage,
    pdf_name: str | None,
) -> None:
    if not pdf_name:
        return

    try:
        storage.delete(pdf_name)
    except Exception:
        logger.exception(
            "Failed to delete uploaded invoice PDF " "after processing error. PDF: %s",
            pdf_name,
        )


def process_simple_invoice(
    *,
    invoice,
    employee_data,
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        xlsx_path = temp_path / (
            f"simple-invoice-IA " f"({invoice.invoice_number}).xlsx"
        )

        generate_simple_invoice_xlsx(
            invoice=invoice,
            employee_data=employee_data,
            output_path=xlsx_path,
        )

        pdf_path = convert_xlsx_to_pdf(
            xlsx_path=xlsx_path,
            output_dir=temp_path,
        )

        uploaded_pdf_name = None
        storage = EmployeeSimpleInvoice._meta.get_field("pdf_file").storage

        expired = False

        try:
            with transaction.atomic():
                locked_invoice = (
                    EmployeeSimpleInvoice.objects.select_for_update()
                    .select_related(
                        "employee",
                    )
                    .get(
                        pk=invoice.pk,
                    )
                )

                if locked_invoice.status != EmployeeSimpleInvoice.Status.PROCESSING:
                    raise (
                        SimpleInvoiceProcessingCancelled(
                            "The invoice is no longer processing."
                        )
                    )

                if is_simple_invoice_processing_expired(locked_invoice):
                    EmployeeWorkHours.objects.filter(
                        invoice=locked_invoice,
                    ).update(
                        invoice=None,
                    )

                    locked_invoice.status = EmployeeSimpleInvoice.Status.FAILED

                    locked_invoice.save(
                        update_fields=[
                            "status",
                        ]
                    )

                    expired = True

                else:
                    with pdf_path.open("rb") as pdf:
                        locked_invoice.pdf_file.save(
                            pdf_path.name,
                            File(pdf),
                            save=False,
                        )

                    uploaded_pdf_name = locked_invoice.pdf_file.name

                    locked_invoice.save(
                        update_fields=[
                            "pdf_file",
                        ]
                    )

                    send_simple_invoice_email(
                        invoice=locked_invoice,
                        pdf_path=pdf_path,
                    )

                    locked_invoice.status = EmployeeSimpleInvoice.Status.SENT

                    locked_invoice.save(
                        update_fields=[
                            "status",
                        ]
                    )

            if expired:
                raise SimpleInvoiceProcessingExpired(
                    "The invoice processing window expired."
                )

        except (
            SimpleInvoiceProcessingCancelled,
            SimpleInvoiceProcessingExpired,
        ):
            raise

        except Exception:
            _delete_uploaded_pdf(
                storage=storage,
                pdf_name=uploaded_pdf_name,
            )

            raise
