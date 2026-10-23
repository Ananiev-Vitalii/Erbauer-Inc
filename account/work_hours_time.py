from datetime import date

from django.utils import timezone

WORK_HOURS_RETENTION_MONTHS = 12


def get_work_hours_cutoff(
    *,
    months: int = WORK_HOURS_RETENTION_MONTHS,
    reference_date: date | None = None,
) -> date:
    if months < 1:
        raise ValueError("Months must be greater than zero.")

    reference_date = reference_date or timezone.localdate()

    month_index = reference_date.year * 12 + reference_date.month - 1 - (months - 1)

    year, zero_based_month = divmod(
        month_index,
        12,
    )

    return date(
        year,
        zero_based_month + 1,
        1,
    )
