import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from account.models import EmployeeSimpleInvoice, EmployeeWorkHours

logger = logging.getLogger(__name__)

SIMPLE_INVOICE_PROCESSING_TIMEOUT = timedelta(minutes=5)
SIMPLE_INVOICE_TASK_EXPIRES_SECONDS = int(
    SIMPLE_INVOICE_PROCESSING_TIMEOUT.total_seconds()
)


class SimpleInvoiceProcessingCancelled(Exception):
    """The invoice is no longer eligible for processing."""


class SimpleInvoiceProcessingExpired(SimpleInvoiceProcessingCancelled):
    """The invoice exceeded the allowed processing window."""


def get_simple_invoice_processing_cutoff():
    return timezone.now() - SIMPLE_INVOICE_PROCESSING_TIMEOUT


def is_simple_invoice_processing_expired(
    invoice: EmployeeSimpleInvoice,
    *,
    now=None,
) -> bool:
    if invoice.status != EmployeeSimpleInvoice.Status.PROCESSING:
        return False

    now = now or timezone.now()

    return invoice.created_at <= now - SIMPLE_INVOICE_PROCESSING_TIMEOUT


def _delete_invoice_pdf_names(
    pdf_names: list[str],
) -> None:
    if not pdf_names:
        return

    storage = EmployeeSimpleInvoice._meta.get_field("pdf_file").storage

    for pdf_name in pdf_names:
        try:
            storage.delete(pdf_name)
        except Exception:
            logger.exception(
                "Failed to delete stale Simple Invoice PDF: %s",
                pdf_name,
            )


def _transition_processing_queryset_to_failed(
    queryset,
    *,
    stale_only: bool,
) -> int:
    if stale_only:
        queryset = queryset.filter(
            created_at__lte=get_simple_invoice_processing_cutoff(),
        )

    pdf_names = []

    with transaction.atomic():
        invoices = list(
            queryset.select_for_update()
            .filter(
                status=EmployeeSimpleInvoice.Status.PROCESSING,
            )
            .only(
                "pk",
                "pdf_file",
            )
        )

        if not invoices:
            return 0

        invoice_ids = [invoice.pk for invoice in invoices]

        pdf_names = [invoice.pdf_file.name for invoice in invoices if invoice.pdf_file]

        EmployeeWorkHours.objects.filter(
            invoice_id__in=invoice_ids,
        ).update(
            invoice=None,
        )

        EmployeeSimpleInvoice.objects.filter(
            pk__in=invoice_ids,
            status=EmployeeSimpleInvoice.Status.PROCESSING,
        ).update(
            status=EmployeeSimpleInvoice.Status.FAILED,
            pdf_file="",
        )

    _delete_invoice_pdf_names(pdf_names)

    return len(invoice_ids)


def mark_simple_invoice_failed(
    *,
    invoice_id: int,
) -> bool:
    transitioned = _transition_processing_queryset_to_failed(
        EmployeeSimpleInvoice.objects.filter(
            pk=invoice_id,
        ),
        stale_only=False,
    )

    return transitioned > 0


def expire_stale_simple_invoice(
    *,
    invoice_id: int,
) -> bool:
    transitioned = _transition_processing_queryset_to_failed(
        EmployeeSimpleInvoice.objects.filter(
            pk=invoice_id,
        ),
        stale_only=True,
    )

    return transitioned > 0


def expire_stale_simple_invoices_for_period(
    *,
    employee,
    start_date,
    end_date,
    exclude_invoice_id: int | None = None,
) -> int:
    if start_date.year != end_date.year or start_date.month != end_date.month:
        raise ValueError("An invoice period must be inside one calendar month.")

    queryset = EmployeeSimpleInvoice.objects.filter(
        employee=employee,
        invoice_year=start_date.year,
        invoice_month=start_date.month,
        start_day__lte=end_date.day,
        end_day__gte=start_date.day,
    )

    if exclude_invoice_id is not None:
        queryset = queryset.exclude(
            pk=exclude_invoice_id,
        )

    return _transition_processing_queryset_to_failed(
        queryset,
        stale_only=True,
    )


def expire_stale_simple_invoices_for_employees_month(
    *,
    employee_ids,
    year: int,
    month: int,
) -> int:
    employee_ids = tuple(employee_ids)

    if not employee_ids:
        return 0

    queryset = EmployeeSimpleInvoice.objects.filter(
        employee_id__in=employee_ids,
        invoice_year=year,
        invoice_month=month,
    )

    return _transition_processing_queryset_to_failed(
        queryset,
        stale_only=True,
    )


def expire_stale_simple_invoices_for_employee(
    *,
    employee,
) -> int:
    return _transition_processing_queryset_to_failed(
        EmployeeSimpleInvoice.objects.filter(
            employee=employee,
        ),
        stale_only=True,
    )


def get_simple_invoice_after_expiration_check(
    *,
    invoice_id: int,
    employee_user_id: int | None = None,
) -> EmployeeSimpleInvoice | None:
    queryset = EmployeeSimpleInvoice.objects.select_related(
        "employee",
    ).filter(
        pk=invoice_id,
    )

    if employee_user_id is not None:
        queryset = queryset.filter(
            employee__user_id=employee_user_id,
        )

    invoice = queryset.first()

    if invoice is None:
        return None

    if not is_simple_invoice_processing_expired(invoice):
        return invoice

    expire_stale_simple_invoice(
        invoice_id=invoice.pk,
    )

    return queryset.first()
