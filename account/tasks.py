import logging

from celery import shared_task

from account.models import (
    EmployeeSimpleInvoice,
    EmployeeWorkHours,
)
from account.services.simple_invoice_period import (
    reserve_work_hours_for_invoice,
)
from account.services.simple_invoice_processing import (
    SimpleInvoiceProcessingCancelled,
    SimpleInvoiceProcessingExpired,
    get_simple_invoice_after_expiration_check,
    mark_simple_invoice_failed,
)
from account.services.simple_invoice_service import (
    process_simple_invoice,
)
from account.simple_invoice_time import (
    SIMPLE_INVOICE_RETENTION_MONTHS,
    get_simple_invoice_cutoff,
)
from account.work_hours_time import (
    get_work_hours_cutoff,
)

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def process_simple_invoice_task(
    invoice_id: int,
    employee_data: dict,
) -> None:
    invoice = get_simple_invoice_after_expiration_check(
        invoice_id=invoice_id,
    )

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

    try:
        reserve_work_hours_for_invoice(
            invoice=invoice,
        )

        process_simple_invoice(
            invoice=invoice,
            employee_data=employee_data,
        )

    except (
        SimpleInvoiceProcessingCancelled,
        SimpleInvoiceProcessingExpired,
    ):
        logger.info(
            "Simple Invoice task stopped because "
            "the invoice is no longer eligible "
            "for processing. Invoice id: %s",
            invoice_id,
        )

        return

    except Exception:
        mark_simple_invoice_failed(
            invoice_id=invoice_id,
        )

        logger.exception(
            "Simple Invoice processing failed. " "Invoice id: %s",
            invoice_id,
        )

        raise


@shared_task(
    name="account.cleanup_expired_simple_invoices",
    ignore_result=True,
)
def cleanup_expired_simple_invoices() -> None:
    cutoff = get_simple_invoice_cutoff(
        months=SIMPLE_INVOICE_RETENTION_MONTHS,
    )

    expired_invoices = EmployeeSimpleInvoice.objects.filter(
        created_at__lt=cutoff,
    )

    (
        deleted_total,
        deleted_by_model,
    ) = expired_invoices.delete()

    deleted_invoices = deleted_by_model.get(
        EmployeeSimpleInvoice._meta.label,
        0,
    )

    logger.info(
        "Simple Invoice retention cleanup completed. "
        "Cutoff: %s. "
        "Invoices deleted: %s. "
        "Total objects deleted: %s.",
        cutoff.isoformat(),
        deleted_invoices,
        deleted_total,
    )


@shared_task(
    name="account.cleanup_expired_work_hours",
    ignore_result=True,
)
def cleanup_expired_work_hours() -> None:
    cutoff = get_work_hours_cutoff()

    expired_work_hours = EmployeeWorkHours.objects.filter(
        work_date__lt=cutoff,
    )

    (
        deleted_total,
        deleted_by_model,
    ) = expired_work_hours.delete()

    deleted_work_hours = deleted_by_model.get(
        EmployeeWorkHours._meta.label,
        0,
    )

    logger.info(
        "Work Hours retention cleanup completed. "
        "Cutoff: %s. "
        "Work Hours deleted: %s. "
        "Total objects deleted: %s.",
        cutoff.isoformat(),
        deleted_work_hours,
        deleted_total,
    )
