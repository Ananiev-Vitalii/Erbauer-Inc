from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from account.models import Employee, EmployeeSimpleInvoice
from account.services.simple_invoice_period import (
    build_invoice_period,
    get_available_invoice_months,
    get_available_invoice_years,
    validate_invoice_period_available,
)
from account.services.simple_invoice_processing import (
    SIMPLE_INVOICE_TASK_EXPIRES_SECONDS,
)
from account.tasks import process_simple_invoice_task


def submit_simple_invoice(
    *,
    employee: Employee,
    invoice_data: dict,
    employee_data: dict,
) -> EmployeeSimpleInvoice:
    """
    Creates and schedules a Simple Invoice safely.

    Calendar work hours are optional. The submitted Hours
    value may be entered manually by the employee.

    Critical period rules are checked again immediately
    before the invoice is stored.

    The Celery task expires in the broker if it is not
    picked up within the allowed processing window.
    """
    today = timezone.localdate()

    invoice_year = invoice_data["invoice_year"]

    invoice_month = invoice_data["invoice_month"]

    start_day = invoice_data["start_day"]

    end_day = invoice_data["end_day"]

    hours = invoice_data["hours"]

    if hours is None or hours <= 0:
        raise ValidationError(_("Hours must be greater " "than zero."))

    available_years = get_available_invoice_years(
        reference_date=today,
    )

    if invoice_year not in available_years:
        raise ValidationError(_("The selected invoice year " "is not available."))

    available_months = get_available_invoice_months(
        year=invoice_year,
        reference_date=today,
    )

    if invoice_month not in available_months:
        raise ValidationError(_("The selected invoice month " "is not available."))

    (
        start_date,
        end_date,
    ) = build_invoice_period(
        year=invoice_year,
        month=invoice_month,
        start_day=start_day,
        end_day=end_day,
    )

    if end_date > today:
        raise ValidationError(_("Invoice period cannot " "include future dates."))

    with transaction.atomic():
        locked_employee = Employee.objects.select_for_update().get(pk=employee.pk)

        validate_invoice_period_available(
            employee=locked_employee,
            start_date=start_date,
            end_date=end_date,
        )

        invoice = EmployeeSimpleInvoice(
            employee=locked_employee,
            invoice_number=invoice_data["invoice_number"],
            invoice_year=invoice_year,
            invoice_month=invoice_month,
            start_day=start_day,
            end_day=end_day,
            hours=hours,
            rate=invoice_data["rate"],
            gst_account_number=invoice_data["gst_account_number"],
            gst=invoice_data["gst"],
            wsbc=invoice_data["wsbc"],
        )

        invoice.full_clean()
        invoice.save()

        process_simple_invoice_task.apply_async_on_commit(
            args=(
                invoice.pk,
                dict(employee_data),
            ),
            expires=(SIMPLE_INVOICE_TASK_EXPIRES_SECONDS),
        )

    return invoice
