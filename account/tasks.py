from __future__ import annotations

import logging

from celery import shared_task
from django.db import DatabaseError, transaction

from account.models import Employee, EmployeeSimpleInvoice, EmployeeWorkHours
from account.services.simple_invoice_period import reserve_work_hours_for_invoice
from account.services.simple_invoice_processing import (
    SimpleInvoiceProcessingCancelled,
    SimpleInvoiceProcessingExpired,
    get_simple_invoice_after_expiration_check,
    mark_simple_invoice_failed,
)
from account.services.simple_invoice_service import process_simple_invoice
from account.simple_invoice_time import (
    SIMPLE_INVOICE_RETENTION_MONTHS,
    get_simple_invoice_cutoff,
)
from account.types import EmployeeAddressData
from account.work_hours_time import get_work_hours_cutoff

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def process_simple_invoice_task(
    invoice_id: int,
    employee_data: EmployeeAddressData,
) -> None:
    invoice = get_simple_invoice_after_expiration_check(invoice_id=invoice_id)

    if invoice is None:
        logger.warning(
            "Simple Invoice task skipped because "
            "invoice does not exist. Invoice id: %s",
            invoice_id,
        )

        return

    if invoice.status != EmployeeSimpleInvoice.Status.PROCESSING:
        logger.info(
            "Simple Invoice task skipped because "
            "invoice is no longer processing. "
            "Invoice id: %s. Status: %s",
            invoice_id,
            invoice.status,
        )

        return

    claimed = False
    try:
        reserve_work_hours_for_invoice(invoice=invoice)
        claimed = True

        process_simple_invoice(invoice=invoice, employee_data=employee_data)

    except (SimpleInvoiceProcessingCancelled, SimpleInvoiceProcessingExpired):
        logger.info(
            "Simple Invoice task stopped because "
            "the invoice is no longer eligible "
            "for processing. Invoice id: %s",
            invoice_id,
        )

        return

    except Exception:
        try:
            mark_simple_invoice_failed(
                invoice_id=invoice_id,
                expected_statuses=(
                    EmployeeSimpleInvoice.Status.PREPARING
                    if claimed
                    else EmployeeSimpleInvoice.Status.PROCESSING,
                ),
            )
        except DatabaseError as error:
            logger.error(
                "Could not confirm failed invoice state (%s). Invoice id: %s",
                type(error).__name__,
                invoice_id,
            )

        raise


@shared_task(name="account.cleanup_expired_simple_invoices", ignore_result=True)
def cleanup_expired_simple_invoices() -> None:
    cutoff = get_simple_invoice_cutoff(months=SIMPLE_INVOICE_RETENTION_MONTHS)

    expired_invoices = EmployeeSimpleInvoice.objects.filter(created_at__lt=cutoff)

    employee_ids = list(
        expired_invoices.order_by("employee_id").values_list("employee_id", flat=True)
        .distinct()
    )
    deleted_total = 0
    deleted_invoices = 0
    for employee_id in employee_ids:
        with transaction.atomic():
            employee = (
                Employee.objects.select_for_update().filter(pk=employee_id).first()
            )
            if employee is None:
                continue
            invoice_ids = list(
                expired_invoices.filter(employee_id=employee_id).order_by("pk")
                .select_for_update()
                .values_list("pk", flat=True)
            )
            total, by_model = EmployeeSimpleInvoice.objects.filter(
                pk__in=invoice_ids
            ).delete()
        deleted_total += total
        deleted_invoices += by_model.get(EmployeeSimpleInvoice._meta.label, 0)

    logger.info(
        "Simple Invoice retention cleanup completed. "
        "Cutoff: %s. "
        "Invoices deleted: %s. "
        "Total objects deleted: %s.",
        cutoff.isoformat(),
        deleted_invoices,
        deleted_total,
    )


@shared_task(name="account.cleanup_expired_work_hours", ignore_result=True)
def cleanup_expired_work_hours() -> None:
    cutoff = get_work_hours_cutoff()

    expired_work_hours = EmployeeWorkHours.objects.filter(work_date__lt=cutoff)

    employee_ids = list(
        expired_work_hours.order_by("employee_id").values_list("employee_id", flat=True)
        .distinct()
    )
    deleted_total = 0
    deleted_work_hours = 0
    for employee_id in employee_ids:
        with transaction.atomic():
            employee = (
                Employee.objects.select_for_update().filter(pk=employee_id).first()
            )
            if employee is None:
                continue
            employee_hours = expired_work_hours.filter(employee_id=employee_id)
            invoice_ids = employee_hours.filter(invoice__isnull=False).values_list(
                "invoice_id", flat=True,
            )
            list(
                EmployeeSimpleInvoice.objects.filter(pk__in=invoice_ids).order_by("pk")
                .select_for_update()
                .values_list("pk", flat=True)
            )
            total, by_model = employee_hours.delete()
        deleted_total += total
        deleted_work_hours += by_model.get(EmployeeWorkHours._meta.label, 0)

    logger.info(
        "Work Hours retention cleanup completed. "
        "Cutoff: %s. "
        "Work Hours deleted: %s. "
        "Total objects deleted: %s.",
        cutoff.isoformat(),
        deleted_work_hours,
        deleted_total,
    )
