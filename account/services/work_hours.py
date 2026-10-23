import calendar
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

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
    get_simple_invoice_processing_cutoff,
)

WORK_HOURS_RETENTION_MONTHS = 12
WORK_HOURS_STEP = Decimal("0.10")
WORK_HOURS_MAX = Decimal("24.00")


def get_month_start(
    value: date,
) -> date:
    return value.replace(day=1)


def shift_month(
    value: date,
    months: int,
) -> date:
    month_index = value.year * 12 + value.month - 1 + months

    year, month_index = divmod(
        month_index,
        12,
    )

    return date(
        year=year,
        month=month_index + 1,
        day=1,
    )


def get_available_work_months(
    *,
    reference_date: date | None = None,
) -> list[date]:
    reference_date = reference_date or timezone.localdate()

    current_month = get_month_start(reference_date)

    return [
        shift_month(
            current_month,
            -offset,
        )
        for offset in range(WORK_HOURS_RETENTION_MONTHS)
    ]


def get_work_hours_retention_cutoff(
    *,
    reference_date: date | None = None,
) -> date:
    reference_date = reference_date or timezone.localdate()

    current_month = get_month_start(reference_date)

    return shift_month(
        current_month,
        -(WORK_HOURS_RETENTION_MONTHS - 1),
    )


def get_month_date_range(
    *,
    year: int,
    month: int,
) -> tuple[date, date]:
    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12.")

    first_day = date(
        year=year,
        month=month,
        day=1,
    )

    last_day = date(
        year=year,
        month=month,
        day=calendar.monthrange(
            year,
            month,
        )[1],
    )

    return first_day, last_day


def parse_work_month(
    value: str,
    *,
    reference_date: date | None = None,
) -> date:
    try:
        (
            year_string,
            month_string,
        ) = value.split(
            "-",
            1,
        )

        selected_month = date(
            year=int(year_string),
            month=int(month_string),
            day=1,
        )

    except (
        AttributeError,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError("Invalid work month. Expected YYYY-MM.") from exc

    available_months = get_available_work_months(
        reference_date=reference_date,
    )

    if selected_month not in available_months:
        raise ValueError(
            "The selected month is outside " "the available work-hours period."
        )

    return selected_month


def _get_active_blocking_invoice_condition() -> Q:
    """
    SENT invoices always block their period.

    PROCESSING invoices block the period only while they
    are inside the allowed processing window.

    Stale PROCESSING invoices are ignored on read-only
    calendar requests. They are converted to FAILED lazily
    when an operation actually needs to modify/check the
    affected invoice period.
    """
    processing_cutoff = get_simple_invoice_processing_cutoff()

    return Q(
        status=EmployeeSimpleInvoice.Status.SENT,
    ) | Q(
        status=EmployeeSimpleInvoice.Status.PROCESSING,
        created_at__gt=processing_cutoff,
    )


def get_employee_month_hours(
    *,
    employee: Employee,
    year: int,
    month: int,
):
    (
        start_date,
        end_date,
    ) = get_month_date_range(
        year=year,
        month=month,
    )

    return (
        EmployeeWorkHours.objects.filter(
            employee=employee,
            work_date__range=(
                start_date,
                end_date,
            ),
        )
        .select_related("invoice")
        .order_by("work_date")
    )


def get_employee_month_hours_map(
    *,
    employee: Employee,
    year: int,
    month: int,
) -> dict[
    date,
    EmployeeWorkHours,
]:
    entries = get_employee_month_hours(
        employee=employee,
        year=year,
        month=month,
    )

    return {entry.work_date: entry for entry in entries}


def _get_effective_month_total(
    *,
    employee: Employee,
    year: int,
    month: int,
) -> Decimal:
    """
    Return the month total shown in the calendar.

    Unlocked periods use EmployeeWorkHours.

    For active PROCESSING/SENT invoice periods, the invoice
    hours are authoritative. The calendar hours inside that
    period are removed from the total and replaced with the
    invoice hours.

    Stale PROCESSING invoices are ignored.
    """
    (
        start_date,
        end_date,
    ) = get_month_date_range(
        year=year,
        month=month,
    )

    work_hours_rows = list(
        EmployeeWorkHours.objects.filter(
            employee=employee,
            work_date__range=(
                start_date,
                end_date,
            ),
        ).values(
            "work_date",
            "hours",
        )
    )

    hours_by_date = {row["work_date"]: row["hours"] for row in work_hours_rows}

    total = sum(
        (row["hours"] for row in work_hours_rows),
        Decimal("0.00"),
    )

    blocking_invoices = (
        EmployeeSimpleInvoice.objects.filter(
            employee=employee,
            invoice_year=year,
            invoice_month=month,
        )
        .filter(_get_active_blocking_invoice_condition())
        .values(
            "start_day",
            "end_day",
            "hours",
        )
        .order_by("start_day")
    )

    for invoice in blocking_invoices:
        calendar_period_total = Decimal("0.00")

        for day_number in range(
            invoice["start_day"],
            invoice["end_day"] + 1,
        ):
            work_date = date(
                year,
                month,
                day_number,
            )

            calendar_period_total += hours_by_date.get(
                work_date,
                Decimal("0.00"),
            )

        invoice_hours = invoice["hours"] or Decimal("0.00")

        total = total - calendar_period_total + invoice_hours

    return total.quantize(Decimal("0.01"))


def get_employee_month_total(
    *,
    employee: Employee,
    year: int,
    month: int,
) -> Decimal:
    return _get_effective_month_total(
        employee=employee,
        year=year,
        month=month,
    )


def get_employee_period_hours(
    *,
    employee: Employee,
    start_date: date,
    end_date: date,
):
    if start_date > end_date:
        raise ValueError("Start date cannot be later than end date.")

    return (
        EmployeeWorkHours.objects.filter(
            employee=employee,
            work_date__range=(
                start_date,
                end_date,
            ),
        )
        .select_related("invoice")
        .order_by("work_date")
    )


def get_employee_period_total(
    *,
    employee: Employee,
    start_date: date,
    end_date: date,
) -> Decimal:
    if start_date > end_date:
        raise ValueError("Start date cannot be later than end date.")

    total = EmployeeWorkHours.objects.filter(
        employee=employee,
        work_date__range=(
            start_date,
            end_date,
        ),
    ).aggregate(total=Sum("hours"))["total"]

    return (total or Decimal("0.00")).quantize(Decimal("0.01"))


def _validate_work_date(
    *,
    work_date: date,
    reference_date: date | None = None,
) -> None:
    reference_date = reference_date or timezone.localdate()

    if work_date > reference_date:
        raise ValidationError(_("Work hours cannot be " "recorded for a future date."))

    retention_cutoff = get_work_hours_retention_cutoff(
        reference_date=reference_date,
    )

    if work_date < retention_cutoff:
        raise ValidationError(
            _("This date is outside " "the available work-hours " "period.")
        )


def _parse_hours_value(
    raw_hours,
) -> Decimal | None:
    if raw_hours is None:
        return None

    value = str(raw_hours).strip()

    if not value:
        return None

    if value.startswith("-"):
        raise ValidationError(_("Hours cannot be negative."))

    normalized_value = value.replace(
        ",",
        ".",
    )

    if not re.fullmatch(
        r"\d+(?:\.\d+)?",
        normalized_value,
    ):
        raise ValidationError(_("Enter hours using numbers " "only, from 0 to 24."))

    if "." in normalized_value:
        decimal_part = normalized_value.split(
            ".",
            1,
        )[1]

        if len(decimal_part) > 2:
            raise ValidationError(_("Hours can have at most " "two decimal places."))

    try:
        hours = Decimal(normalized_value)

    except InvalidOperation as exc:
        raise ValidationError(_("Enter a valid number " "of hours.")) from exc

    if not hours.is_finite():
        raise ValidationError(_("Enter a valid number " "of hours."))

    if hours < 0:
        raise ValidationError(_("Hours cannot be negative."))

    if hours > WORK_HOURS_MAX:
        raise ValidationError(_("Hours cannot exceed " "24 hours per day."))

    if hours == 0:
        return None

    if hours % WORK_HOURS_STEP != Decimal("0.00"):
        raise ValidationError(_("Hours must be entered " "in 0.10-hour increments."))

    return hours.quantize(Decimal("0.01"))


def save_employee_work_hours(
    *,
    employee: Employee,
    work_date: date,
    raw_hours,
) -> EmployeeWorkHours | None:
    _validate_work_date(
        work_date=work_date,
    )

    hours = _parse_hours_value(raw_hours)

    with transaction.atomic():
        locked_employee = Employee.objects.select_for_update().get(pk=employee.pk)

        from account.services.simple_invoice_period import (
            is_work_date_locked,
        )

        if is_work_date_locked(
            employee=locked_employee,
            work_date=work_date,
        ):
            raise ValidationError(
                _(
                    "This date is locked "
                    "because it belongs to "
                    "an invoice that is being "
                    "processed or has already "
                    "been sent."
                )
            )

        entry = (
            EmployeeWorkHours.objects.select_for_update()
            .filter(
                employee=locked_employee,
                work_date=work_date,
            )
            .first()
        )

        if entry and entry.invoice_id:
            raise ValidationError(
                _(
                    "These work hours are "
                    "linked to an invoice "
                    "and cannot be changed."
                )
            )

        if hours is None:
            if entry:
                entry.delete()

            return None

        if entry is None:
            entry = EmployeeWorkHours(
                employee=locked_employee,
                work_date=work_date,
                hours=hours,
            )

        else:
            entry.hours = hours

        entry.full_clean()
        entry.save()

        return entry


def _build_calendar_weeks(
    *,
    year: int,
    month: int,
    entries: dict[
        date,
        Decimal,
    ],
    locked_dates: set[date],
    hidden_hours_dates: set[date],
    can_edit: bool,
    reference_date: date,
) -> list[list[dict]]:
    month_calendar = calendar.Calendar(
        firstweekday=0,
    ).monthdatescalendar(
        year,
        month,
    )

    weeks = []

    for week in month_calendar:
        calendar_week = []

        for work_date in week:
            if work_date.month != month:
                calendar_week.append(
                    {
                        "in_month": False,
                        "date": work_date,
                    }
                )

                continue

            stored_hours = entries.get(work_date)

            hide_hours = work_date in hidden_hours_dates

            display_hours = None if hide_hours else stored_hours

            is_future = work_date > reference_date

            is_locked = work_date in locked_dates

            calendar_week.append(
                {
                    "in_month": True,
                    "date": work_date,
                    "date_value": work_date.isoformat(),
                    "day": work_date.day,
                    "hours": (
                        format(
                            display_hours,
                            ".2f",
                        )
                        if (display_hours is not None)
                        else ""
                    ),
                    "has_hours": (display_hours is not None),
                    "is_weekend": (work_date.weekday() >= 5),
                    "is_today": (work_date == reference_date),
                    "is_future": is_future,
                    "is_locked": is_locked,
                    "can_edit": (can_edit and not is_future and not is_locked),
                }
            )

        weeks.append(calendar_week)

    return weeks


def build_work_hours_calendars(
    *,
    employees: list[Employee],
    year: int,
    month: int,
    current_employee: Employee,
    reference_date: date | None = None,
) -> list[dict]:
    if not employees:
        return []

    reference_date = reference_date or timezone.localdate()

    (
        start_date,
        end_date,
    ) = get_month_date_range(
        year=year,
        month=month,
    )

    employee_ids = [employee.pk for employee in employees]

    work_hours_rows = list(
        EmployeeWorkHours.objects.filter(
            employee_id__in=employee_ids,
            work_date__range=(
                start_date,
                end_date,
            ),
        )
        .values(
            "employee_id",
            "work_date",
            "hours",
        )
        .order_by(
            "employee_id",
            "work_date",
        )
    )

    hours_by_employee = defaultdict(dict)

    raw_totals_by_employee = defaultdict(lambda: Decimal("0.00"))

    for row in work_hours_rows:
        employee_id = row["employee_id"]

        work_date = row["work_date"]

        hours = row["hours"]

        hours_by_employee[employee_id][work_date] = hours

        raw_totals_by_employee[employee_id] += hours

    blocking_invoice_rows = list(
        EmployeeSimpleInvoice.objects.filter(
            employee_id__in=employee_ids,
            invoice_year=year,
            invoice_month=month,
        )
        .filter(_get_active_blocking_invoice_condition())
        .values(
            "employee_id",
            "start_day",
            "end_day",
            "hours",
        )
        .order_by(
            "employee_id",
            "start_day",
        )
    )

    locked_dates_by_employee = defaultdict(set)

    hidden_hours_dates_by_employee = defaultdict(set)

    effective_totals_by_employee = {
        employee_id: total
        for (
            employee_id,
            total,
        ) in raw_totals_by_employee.items()
    }

    for invoice in blocking_invoice_rows:
        employee_id = invoice["employee_id"]

        employee_hours = hours_by_employee.get(
            employee_id,
            {},
        )

        period_dates = []

        calendar_period_total = Decimal("0.00")

        for day_number in range(
            invoice["start_day"],
            invoice["end_day"] + 1,
        ):
            work_date = date(
                year,
                month,
                day_number,
            )

            period_dates.append(work_date)

            locked_dates_by_employee[employee_id].add(work_date)

            calendar_period_total += employee_hours.get(
                work_date,
                Decimal("0.00"),
            )

        calendar_period_total = calendar_period_total.quantize(Decimal("0.01"))

        invoice_hours = (invoice["hours"] or Decimal("0.00")).quantize(Decimal("0.01"))

        current_effective_total = effective_totals_by_employee.get(
            employee_id,
            Decimal("0.00"),
        )

        effective_totals_by_employee[employee_id] = (
            current_effective_total - calendar_period_total + invoice_hours
        )

        if calendar_period_total != invoice_hours:
            hidden_hours_dates_by_employee[employee_id].update(period_dates)

    calendars = []

    for employee in employees:
        employee_hours = hours_by_employee.get(
            employee.pk,
            {},
        )

        locked_dates = locked_dates_by_employee.get(
            employee.pk,
            set(),
        )

        hidden_hours_dates = hidden_hours_dates_by_employee.get(
            employee.pk,
            set(),
        )

        total = (
            effective_totals_by_employee.get(
                employee.pk,
                Decimal("0.00"),
            )
        ).quantize(Decimal("0.01"))

        can_edit = employee.pk == current_employee.pk

        calendars.append(
            {
                "employee": employee,
                "can_edit": can_edit,
                "weeks": _build_calendar_weeks(
                    year=year,
                    month=month,
                    entries=employee_hours,
                    locked_dates=locked_dates,
                    hidden_hours_dates=(hidden_hours_dates),
                    can_edit=can_edit,
                    reference_date=(reference_date),
                ),
                "total": total,
            }
        )

    return calendars
