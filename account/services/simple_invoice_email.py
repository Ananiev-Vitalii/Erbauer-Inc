from pathlib import Path

from django.conf import settings

from account.models import EmployeeSimpleInvoice
from core.services.email import EmailAttachment, EmailPayload, send_html_email
from user.services.email import get_email_company_name


def send_simple_invoice_email(
    *,
    invoice: EmployeeSimpleInvoice,
    pdf_path: Path,
) -> None:
    employee = invoice.employee
    company_name = get_email_company_name()

    pdf_content = pdf_path.read_bytes()
    pdf_filename = pdf_path.name

    recipients = [settings.SIMPLE_INVOICE_RECIPIENT_EMAIL, employee.email]

    payload = EmailPayload(
        subject=f"{employee.first_name} {employee.last_name}"
        f" / Simple Invoice IA ({invoice.invoice_number})",
        template_name="account/emails/simple_invoice.html",
        context={
            "invoice": invoice,
            "employee": employee,
            "company_name": company_name,
        },
        to=recipients,
        attachments=[
            EmailAttachment(
                filename=pdf_filename,
                content=pdf_content,
                mimetype="application/pdf",
            )
        ],
    )

    send_html_email(payload)
