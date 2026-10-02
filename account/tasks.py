from celery import shared_task

from account.models import EmployeeSimpleInvoice
from account.services.simple_invoice_service import process_simple_invoice


@shared_task(ignore_result=True)
def process_simple_invoice_task(
    invoice_id: int,
    employee_data: dict,
) -> None:
    invoice = EmployeeSimpleInvoice.objects.select_related("employee").get(
        id=invoice_id
    )

    process_simple_invoice(
        invoice=invoice,
        employee_data=employee_data,
    )
