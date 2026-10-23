import calendar

from django.utils import timezone

SIMPLE_INVOICE_RETENTION_MONTHS = 36


def get_simple_invoice_cutoff(*, months: int):
    if months < 1:
        raise ValueError("Months must be greater than zero.")

    now = timezone.localtime()

    month_index = now.year * 12 + now.month - 1 - months

    year, month_index = divmod(month_index, 12)
    month = month_index + 1

    day = min(
        now.day,
        calendar.monthrange(year, month)[1],
    )

    return now.replace(
        year=year,
        month=month,
        day=day,
    )
