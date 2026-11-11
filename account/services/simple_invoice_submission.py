from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from kombu.exceptions import OperationalError
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    TimeoutError as RedisTimeoutError,
)

from account.models import Employee, EmployeeSimpleInvoice
from account.services.simple_invoice_period import (
    build_invoice_period,
    get_available_invoice_months,
    get_available_invoice_years,
    validate_invoice_period_available,
)
from account.services.simple_invoice_processing import (
    SIMPLE_INVOICE_TASK_EXPIRES_SECONDS,
    mark_simple_invoice_failed,
)
from account.tasks import process_simple_invoice_task
from account.types import EmployeeAddressData, InvoiceData

logger = logging.getLogger(__name__)


class SimpleInvoicePublicationError(Exception):
    """The invoice was committed, but publishing needs a controlled response."""


def submit_simple_invoice(
    *,
    employee: Employee,
    invoice_data: InvoiceData,
    employee_data: EmployeeAddressData,
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
        raise ValidationError(_("Hours must be greater than zero."))

    available_years = get_available_invoice_years(reference_date=today)

    if invoice_year not in available_years:
        raise ValidationError(_("The selected invoice year is not available."))

    available_months = get_available_invoice_months(
        year=invoice_year,
        reference_date=today,
    )

    if invoice_month not in available_months:
        raise ValidationError(_("The selected invoice month is not available."))

    (start_date, end_date) = build_invoice_period(
        year=invoice_year,
        month=invoice_month,
        start_day=start_day,
        end_day=end_day,
    )

    if end_date > today:
        raise ValidationError(_("Invoice period cannot include future dates."))

    publication_failed = False
    status_unconfirmed = False

    def publish_invoice() -> None:
        nonlocal publication_failed, status_unconfirmed
        try:
            process_simple_invoice_task.apply_async(
                args=(invoice.pk, dict(employee_data)),
                expires=SIMPLE_INVOICE_TASK_EXPIRES_SECONDS,
            )
        except (OperationalError, RedisConnectionError, RedisTimeoutError) as error:
            publication_failed = True
            logger.error(
                "Failed to publish invoice task (%s). Invoice id: %s",
                type(error).__name__,
                invoice.pk,
            )
            try:
                mark_simple_invoice_failed(
                    invoice_id=invoice.pk,
                    expected_statuses=(EmployeeSimpleInvoice.Status.PROCESSING,),
                )
                invoice.refresh_from_db(fields=["status"])
            except (DatabaseError, EmployeeSimpleInvoice.DoesNotExist) as state_error:
                status_unconfirmed = True
                logger.error(
                    "Could not confirm invoice state after publication error (%s). "
                    "Invoice id: %s",
                    type(state_error).__name__,
                    invoice.pk,
                )

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

        transaction.on_commit(publish_invoice)

    if publication_failed:
        if status_unconfirmed:
            raise SimpleInvoicePublicationError(
                _(
                    "Your invoice was saved, but its processing status could not be "
                    "confirmed. Check your invoice history before submitting again."
                )
            )
        if invoice.status == EmployeeSimpleInvoice.Status.FAILED:
            raise SimpleInvoicePublicationError(
                _("Your invoice was saved, but processing failed. Please try again.")
            )

    return invoice
