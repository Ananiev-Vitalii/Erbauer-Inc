from datetime import date as Date
from decimal import Decimal
from typing import TYPE_CHECKING, NotRequired, TypedDict

if TYPE_CHECKING:
    from account.models import Employee


class EmployeeAddressData(TypedDict):
    street_address: str
    city: str
    province: str
    postal_code: str


class InvoiceData(TypedDict):
    invoice_number: int
    invoice_year: int
    invoice_month: int
    start_day: int
    end_day: int
    hours: Decimal
    rate: Decimal
    gst_account_number: str
    gst: Decimal
    wsbc: Decimal


class InvoicePeriodData(TypedDict):
    year: int
    month: int
    start_day: int
    end_day: int
    hours: Decimal


class CalendarDay(TypedDict):
    in_month: bool
    date: Date
    date_value: NotRequired[str]
    day: NotRequired[int]
    hours: NotRequired[str]
    has_hours: NotRequired[bool]
    is_weekend: NotRequired[bool]
    is_today: NotRequired[bool]
    is_future: NotRequired[bool]
    is_locked: NotRequired[bool]
    can_edit: NotRequired[bool]


class EmployeeCalendar(TypedDict):
    employee: "Employee"
    can_edit: bool
    weeks: list[list[CalendarDay]]
    total: Decimal
