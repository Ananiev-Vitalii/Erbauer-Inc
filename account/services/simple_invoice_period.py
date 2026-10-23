from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from account.models import (
    Employee,
    EmployeeSimpleInvoice,
    EmployeeWorkHours,
)
from account.services.simple_invoice_processing import (
    SimpleInvoiceProcessingCancelled,
    expire_stale_simple_invoices_for_employees_month,
    expire_stale_simple_invoices_for_period,
    get_simple_invoice_processing_cutoff,
)
from account.services.work_hours import get_available_work_months

BLOCKING_INVOICE_STATUSES = (
    EmployeeSimpleInvoice.Status.PROCESSING,
    EmployeeSimpleInvoice.Status.SENT,
)


def _get_employee_filter(
    *,
    employee: Employee | None = None,
    employee_user_id: int | None = None,
) -> dict:
    if employee is not None:
        return {
            "employee": employee,
        }

    if employee_user_id is not None:
        return {
            "employee__user_id": employee_user_id,
        }

    raise ValueError("Either employee or employee_user_id must be provided.")


def get_available_invoice_years(
    *,
    reference_date: date | None = None,
) -> tuple[int, ...]:
    available_months = get_available_work_months(
        reference_date=reference_date,
    )

    return tuple(dict.fromkeys(month.year for month in available_months))


def get_available_invoice_months(
    *,
    year: int,
    reference_date: date | None = None,
) -> list[int]:
    available_months = get_available_work_months(
        reference_date=reference_date,
    )

    return sorted(month.month for month in available_months if month.year == year)


def build_invoice_period(
    *,
    year: int,
    month: int,
    start_day: int,
    end_day: int,
) -> tuple[date, date]:
    if start_day > end_day:
        raise ValidationError(_("End day cannot be earlier " "than start day."))

    try:
        start_date = date(
            year,
            month,
            start_day,
        )

        end_date = date(
            year,
            month,
            end_day,
        )

    except ValueError as exc:
        raise ValidationError(_("The selected invoice period " "is invalid.")) from exc

    return start_date, end_date


def get_conflicting_invoices(
    *,
    start_date: date,
    end_date: date,
    employee: Employee | None = None,
    employee_user_id: int | None = None,
    exclude_invoice_id: int | None = None,
):
    if start_date.year != end_date.year or start_date.month != end_date.month:
        raise ValueError("An invoice period must be " "inside one calendar month.")

    employee_filter = _get_employee_filter(
        employee=employee,
        employee_user_id=employee_user_id,
    )

    queryset = EmployeeSimpleInvoice.objects.filter(
        **employee_filter,
        invoice_year=start_date.year,
        invoice_month=start_date.month,
        status__in=BLOCKING_INVOICE_STATUSES,
        start_day__lte=end_date.day,
        end_day__gte=start_date.day,
    )

    if exclude_invoice_id is not None:
        queryset = queryset.exclude(
            pk=exclude_invoice_id,
        )

    return queryset


def get_invoice_period_conflict_status(
    *,
    start_date: date,
    end_date: date,
    employee: Employee | None = None,
    employee_user_id: int | None = None,
    exclude_invoice_id: int | None = None,
    cleanup_stale: bool = True,
) -> str | None:
    if cleanup_stale:
        if employee is None:
            raise ValueError("employee is required when cleanup_stale=True.")

        expire_stale_simple_invoices_for_period(
            employee=employee,
            start_date=start_date,
            end_date=end_date,
            exclude_invoice_id=exclude_invoice_id,
        )

    queryset = get_conflicting_invoices(
        employee=employee,
        employee_user_id=employee_user_id,
        start_date=start_date,
        end_date=end_date,
        exclude_invoice_id=exclude_invoice_id,
    )

    if not cleanup_stale:
        processing_cutoff = get_simple_invoice_processing_cutoff()

        queryset = queryset.filter(
            Q(
                status=EmployeeSimpleInvoice.Status.SENT,
            )
            | Q(
                status=EmployeeSimpleInvoice.Status.PROCESSING,
                created_at__gt=processing_cutoff,
            )
        )

    statuses = set(
        queryset.values_list(
            "status",
            flat=True,
        )
    )

    if EmployeeSimpleInvoice.Status.SENT in statuses:
        return EmployeeSimpleInvoice.Status.SENT

    if EmployeeSimpleInvoice.Status.PROCESSING in statuses:
        return EmployeeSimpleInvoice.Status.PROCESSING

    return None


def invoice_period_has_conflict(
    *,
    employee: Employee,
    start_date: date,
    end_date: date,
    exclude_invoice_id: int | None = None,
) -> bool:
    return (
        get_invoice_period_conflict_status(
            employee=employee,
            start_date=start_date,
            end_date=end_date,
            exclude_invoice_id=exclude_invoice_id,
        )
        is not None
    )


def validate_invoice_period_available(
    *,
    start_date: date,
    end_date: date,
    employee: Employee | None = None,
    employee_user_id: int | None = None,
    exclude_invoice_id: int | None = None,
    cleanup_stale: bool = True,
) -> None:
    conflict_status = get_invoice_period_conflict_status(
        employee=employee,
        employee_user_id=employee_user_id,
        start_date=start_date,
        end_date=end_date,
        exclude_invoice_id=exclude_invoice_id,
        cleanup_stale=cleanup_stale,
    )

    if conflict_status == EmployeeSimpleInvoice.Status.SENT:
        raise ValidationError(_("The selected period has " "already been invoiced."))

    if conflict_status == EmployeeSimpleInvoice.Status.PROCESSING:
        raise ValidationError(_("The selected period is " "currently being processed."))


def is_work_date_locked(
    *,
    employee: Employee,
    work_date: date,
) -> bool:
    expire_stale_simple_invoices_for_period(
        employee=employee,
        start_date=work_date,
        end_date=work_date,
    )

    return EmployeeSimpleInvoice.objects.filter(
        employee=employee,
        invoice_year=work_date.year,
        invoice_month=work_date.month,
        start_day__lte=work_date.day,
        end_day__gte=work_date.day,
        status__in=BLOCKING_INVOICE_STATUSES,
    ).exists()


def get_locked_work_dates(
    *,
    employee: Employee,
    year: int,
    month: int,
) -> set[date]:
    expire_stale_simple_invoices_for_employees_month(
        employee_ids=(employee.pk,),
        year=year,
        month=month,
    )

    invoices = EmployeeSimpleInvoice.objects.filter(
        employee=employee,
        invoice_year=year,
        invoice_month=month,
        status__in=BLOCKING_INVOICE_STATUSES,
    ).values_list(
        "start_day",
        "end_day",
    )

    locked_dates = set()

    for (
        start_day,
        end_day,
    ) in invoices:
        for day in range(
            start_day,
            end_day + 1,
        ):
            locked_dates.add(
                date(
                    year,
                    month,
                    day,
                )
            )

    return locked_dates


def get_invoice_period_hours_total(
    *,
    start_date: date,
    end_date: date,
    employee: Employee | None = None,
    employee_user_id: int | None = None,
) -> Decimal:
    if start_date > end_date:
        raise ValueError("Start date cannot be later " "than end date.")

    employee_filter = _get_employee_filter(
        employee=employee,
        employee_user_id=employee_user_id,
    )

    processing_cutoff = get_simple_invoice_processing_cutoff()

    available_hours = EmployeeWorkHours.objects.filter(
        **employee_filter,
        work_date__range=(
            start_date,
            end_date,
        ),
    ).filter(
        Q(invoice__isnull=True)
        | Q(invoice__status=(EmployeeSimpleInvoice.Status.FAILED))
        | Q(
            invoice__status=(EmployeeSimpleInvoice.Status.PROCESSING),
            invoice__created_at__lte=processing_cutoff,
        )
    )

    total = available_hours.aggregate(
        total=Sum("hours"),
    )["total"]

    return (total or Decimal("0.00")).quantize(Decimal("0.01"))


def get_initial_invoice_period(
    *,
    employee: Employee,
    reference_date: date | None = None,
) -> dict:
    reference_date = reference_date or timezone.localdate()

    start_date = reference_date.replace(day=1)

    hours = get_invoice_period_hours_total(
        employee=employee,
        start_date=start_date,
        end_date=reference_date,
    )

    return {
        "year": reference_date.year,
        "month": reference_date.month,
        "start_day": 1,
        "end_day": reference_date.day,
        "hours": hours,
    }


def reserve_work_hours_for_invoice(
    *,
    invoice: EmployeeSimpleInvoice,
) -> int:
    if not invoice.pk:
        raise ValueError(
            "The invoice must be saved " "before work hours can be reserved."
        )

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
            raise SimpleInvoiceProcessingCancelled(
                "The invoice is no longer processing."
            )

        start_date = locked_invoice.period_start

        end_date = locked_invoice.period_end

        validate_invoice_period_available(
            employee=locked_invoice.employee,
            start_date=start_date,
            end_date=end_date,
            exclude_invoice_id=locked_invoice.pk,
        )

        work_hours = EmployeeWorkHours.objects.select_for_update().filter(
            employee=locked_invoice.employee,
            work_date__range=(
                start_date,
                end_date,
            ),
            invoice__isnull=True,
        )

        return work_hours.update(
            invoice=locked_invoice,
        )


def release_work_hours_from_invoice(
    *,
    invoice: EmployeeSimpleInvoice,
) -> int:
    with transaction.atomic():
        return (
            EmployeeWorkHours.objects.select_for_update()
            .filter(
                invoice=invoice,
            )
            .update(
                invoice=None,
            )
        )
