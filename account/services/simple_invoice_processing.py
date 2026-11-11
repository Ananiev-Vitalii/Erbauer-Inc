from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from functools import partial

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from account.models import Employee, EmployeeSimpleInvoice, EmployeeWorkHours

logger = logging.getLogger(__name__)

SIMPLE_INVOICE_PROCESSING_TIMEOUT = timedelta(minutes=5)
SIMPLE_INVOICE_TASK_EXPIRES_SECONDS = int(
    SIMPLE_INVOICE_PROCESSING_TIMEOUT.total_seconds()
)
ACTIVE_INVOICE_STATUSES = (
    EmployeeSimpleInvoice.Status.PROCESSING,
    EmployeeSimpleInvoice.Status.PREPARING,
)


class SimpleInvoiceProcessingCancelled(Exception):
    """The invoice is no longer eligible for processing."""


class SimpleInvoiceProcessingExpired(SimpleInvoiceProcessingCancelled):
    """The invoice exceeded the allowed processing window."""


def get_simple_invoice_processing_cutoff() -> datetime:
    return timezone.now() - SIMPLE_INVOICE_PROCESSING_TIMEOUT


def is_simple_invoice_processing_expired(
    invoice: EmployeeSimpleInvoice,
    *,
    now: datetime | None = None,
) -> bool:
    if invoice.status not in ACTIVE_INVOICE_STATUSES:
        return False

    now = now or timezone.now()

    return invoice.created_at <= now - SIMPLE_INVOICE_PROCESSING_TIMEOUT


def lock_simple_invoice(
    *,
    invoice_id: int,
    employee_id: int,
) -> EmployeeSimpleInvoice | None:
    """Lock Employee before Invoice inside the caller's transaction."""
    employee = Employee.objects.select_for_update().filter(pk=employee_id).first()
    if employee is None:
        return None

    invoice = (
        EmployeeSimpleInvoice.objects.select_for_update()
        .filter(pk=invoice_id, employee_id=employee_id)
        .first()
    )
    if invoice is not None:
        invoice.employee = employee
    return invoice


def _delete_invoice_pdf_names(pdf_files: list[tuple[int, str]]) -> None:
    if not pdf_files:
        return

    storage = EmployeeSimpleInvoice._meta.get_field("pdf_file").storage

    for invoice_id, pdf_name in pdf_files:
        try:
            storage.delete(pdf_name)
        except Exception as error:
            logger.exception(
                "Failed to delete stale invoice PDF (%s). Invoice id: %s",
                type(error).__name__,
                invoice_id,
            )


def _transition_processing_queryset_to_failed(
    queryset: QuerySet[EmployeeSimpleInvoice],
    *,
    stale_only: bool,
    expected_statuses: tuple[str, ...] = ACTIVE_INVOICE_STATUSES,
) -> int:
    queryset = queryset.filter(status__in=expected_statuses)
    if stale_only:
        queryset = queryset.filter(
            created_at__lte=get_simple_invoice_processing_cutoff(),
        )

    candidates = list(
        queryset.order_by("employee_id", "pk").values_list("pk", "employee_id")
    )
    if not candidates:
        return 0

    with transaction.atomic():
        employee_ids = sorted({employee_id for _, employee_id in candidates})
        locked_employee_ids = list(
            Employee.objects.filter(pk__in=employee_ids).order_by("pk")
            .select_for_update()
            .values_list("pk", flat=True)
        )
        invoices = list(
            queryset.select_related(None)
            .filter(
                pk__in=[invoice_id for invoice_id, _ in candidates],
                employee_id__in=locked_employee_ids,
            )
            .order_by("pk")
            .select_for_update(of=("self",))
            .only(
                "pk",
                "pdf_file",
            )
        )

        if not invoices:
            return 0

        invoice_ids = [invoice.pk for invoice in invoices]

        pdf_files = [
            (invoice.pk, invoice.pdf_file.name)
            for invoice in invoices
            if invoice.pdf_file
        ]

        EmployeeWorkHours.objects.filter(invoice_id__in=invoice_ids).update(
            invoice=None,
        )

        EmployeeSimpleInvoice.objects.filter(
            pk__in=invoice_ids,
            status__in=expected_statuses,
        ).update(
            status=EmployeeSimpleInvoice.Status.FAILED,
            pdf_file="",
        )

        transaction.on_commit(partial(_delete_invoice_pdf_names, pdf_files))

    return len(invoice_ids)


def mark_simple_invoice_failed(
    *,
    invoice_id: int,
    expected_statuses: tuple[str, ...] = ACTIVE_INVOICE_STATUSES,
) -> bool:
    transitioned = _transition_processing_queryset_to_failed(
        EmployeeSimpleInvoice.objects.filter(pk=invoice_id),
        stale_only=False,
        expected_statuses=expected_statuses,
    )

    return transitioned > 0


def check_preparing_simple_invoice(
    *,
    invoice_id: int,
    employee_id: int,
) -> EmployeeSimpleInvoice:
    """Check the current claim and deadline before an external email call."""
    with transaction.atomic():
        invoice = lock_simple_invoice(invoice_id=invoice_id, employee_id=employee_id)
        if invoice is None or invoice.status != EmployeeSimpleInvoice.Status.PREPARING:
            raise SimpleInvoiceProcessingCancelled("The invoice is not preparing.")

        expired = is_simple_invoice_processing_expired(invoice)
        if expired:
            mark_simple_invoice_failed(
                invoice_id=invoice.pk,
                expected_statuses=(EmployeeSimpleInvoice.Status.PREPARING,),
            )

    if expired:
        raise SimpleInvoiceProcessingExpired("The invoice processing window expired.")
    return invoice


def mark_simple_invoice_sent(
    *,
    invoice_id: int,
    employee_id: int,
    pdf_name: str,
) -> None:
    """Finalize only a current, unexpired claim after provider acceptance."""
    with transaction.atomic():
        invoice = lock_simple_invoice(invoice_id=invoice_id, employee_id=employee_id)
        if invoice is None or invoice.status != EmployeeSimpleInvoice.Status.PREPARING:
            raise SimpleInvoiceProcessingCancelled("The invoice is not preparing.")

        expired = is_simple_invoice_processing_expired(invoice)
        if expired:
            mark_simple_invoice_failed(
                invoice_id=invoice.pk,
                expected_statuses=(EmployeeSimpleInvoice.Status.PREPARING,),
            )
        else:
            invoice.pdf_file = pdf_name
            invoice.status = EmployeeSimpleInvoice.Status.SENT
            invoice.save(update_fields=["pdf_file", "status"])

    if expired:
        raise SimpleInvoiceProcessingExpired("The invoice processing window expired.")


def expire_stale_simple_invoice(*, invoice_id: int) -> bool:
    transitioned = _transition_processing_queryset_to_failed(
        EmployeeSimpleInvoice.objects.filter(pk=invoice_id),
        stale_only=True,
    )

    return transitioned > 0


def expire_stale_simple_invoices_for_period(
    *,
    employee: Employee,
    start_date: date,
    end_date: date,
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
        queryset = queryset.exclude(pk=exclude_invoice_id)

    return _transition_processing_queryset_to_failed(queryset, stale_only=True)


def expire_stale_simple_invoices_for_employees_month(
    *,
    employee_ids: Iterable[int],
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

    return _transition_processing_queryset_to_failed(queryset, stale_only=True)


def expire_stale_simple_invoices_for_employee(*, employee: Employee | int) -> int:
    return _transition_processing_queryset_to_failed(
        EmployeeSimpleInvoice.objects.filter(employee=employee),
        stale_only=True,
    )


def get_simple_invoice_after_expiration_check(
    *,
    invoice_id: int,
    employee_user_id: int | None = None,
) -> EmployeeSimpleInvoice | None:
    queryset = EmployeeSimpleInvoice.objects.select_related("employee").filter(
        pk=invoice_id,
    )

    if employee_user_id is not None:
        queryset = queryset.filter(employee__user_id=employee_user_id)

    invoice = queryset.first()

    if invoice is None:
        return None

    if not is_simple_invoice_processing_expired(invoice):
        return invoice

    expire_stale_simple_invoice(invoice_id=invoice.pk)

    return queryset.first()
