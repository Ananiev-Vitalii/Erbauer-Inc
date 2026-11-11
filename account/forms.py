from __future__ import annotations

import calendar
import re
from decimal import Decimal
from typing import Any, Literal, overload

from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.db.models.fields.files import FieldFile
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from account.models import CanadianProvince, Employee, EmployeeSimpleInvoice, Profile
from account.services.simple_invoice_period import (
    build_invoice_period,
    get_available_invoice_months,
    get_available_invoice_years,
    validate_invoice_period_available,
)
from account.validators import (
    canadian_postal_code_validator,
    normalize_canadian_postal_code,
)

PHONE_ERROR_MESSAGE = _(
    "Enter a 10-digit Canadian or US phone number, optionally prefixed with +1 or 1."
)


class EmployeeContactForm(forms.ModelForm):
    phone = forms.CharField(
        required=False,
        max_length=17,
        label=_("Phone"),
        error_messages={"max_length": PHONE_ERROR_MESSAGE},
    )

    class Meta:
        model = Employee
        fields = ["phone", "email", "street_address", "city", "province", "postal_code"]

    def clean_phone(self) -> str:
        phone = self.cleaned_data.get("phone", "")
        if not phone:
            return ""
        match = re.fullmatch(
            r"(?:\+?1 ?)?("
            r"[0-9]{10}|[0-9]{3}([ .-])[0-9]{3}\2[0-9]{4}|"
            r"\([0-9]{3}\) [0-9]{3}-[0-9]{4})",
            phone,
        )
        if match is None:
            raise forms.ValidationError(PHONE_ERROR_MESSAGE, code="invalid")
        national_number = re.sub(r"[ ().-]", "", match.group(1))
        return f"+1{national_number}"

    def clean_street_address(self) -> str:
        street_address = self.cleaned_data.get("street_address", "")
        return street_address.strip()

    def clean_city(self) -> str:
        city = self.cleaned_data.get("city", "").strip()

        if not city:
            return ""

        return city[:1].upper() + city[1:]

    def clean_postal_code(self) -> str:
        return normalize_canadian_postal_code(self.cleaned_data.get("postal_code", ""))


class EmployeePositionForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = Employee
        fields = ["position"]


class ProfileAvatarForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["avatar"]

    def clean_avatar(self) -> UploadedFile | FieldFile | Literal[False] | None:
        avatar = self.cleaned_data.get("avatar")

        if not isinstance(avatar, UploadedFile):
            return avatar

        allowed_types = ["image/jpeg", "image/png", "image/webp"]

        if avatar.content_type not in allowed_types:
            raise forms.ValidationError(_("Please upload a JPG, PNG, or WEBP image."))

        max_size = 5 * 1024 * 1024

        if avatar.size > max_size:
            raise forms.ValidationError(_("Avatar image must be smaller than 5 MB."))

        return avatar


class SimpleInvoiceForm(forms.ModelForm):
    invoice_year = forms.TypedChoiceField(
        label=_("Invoice year"),
        choices=(),
        coerce=int,
    )

    class Meta:
        model = EmployeeSimpleInvoice
        fields = [
            "invoice_number",
            "invoice_year",
            "invoice_month",
            "start_day",
            "end_day",
            "hours",
            "rate",
            "gst_account_number",
            "gst",
            "wsbc",
        ]

    def __init__(
        self,
        *args: Any,
        employee: Employee | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        self.employee = employee
        self.today = timezone.localdate()

        self.fields["start_day"].required = True
        self.fields["end_day"].required = True
        self.fields["hours"].required = True
        self.fields["gst_account_number"].required = False
        self.fields["gst"].required = True
        self.fields["wsbc"].required = True

        self._configure_period_fields()

    def _get_raw_field_value(
        self,
        field_name: str,
        default: int | None = None,
    ) -> str | int | None:
        if self.is_bound:
            value = self.data.get(self.add_prefix(field_name))

            if value not in (None, ""):
                return value

        value = self.initial.get(field_name, default)

        if value not in (None, ""):
            return value

        return default

    @staticmethod
    @overload
    def _to_int(value: str | int | None, default: int) -> int:
        ...

    @staticmethod
    @overload
    def _to_int(value: str | int | None, default: None = None) -> int | None:
        ...

    @staticmethod
    def _to_int(value: str | int | None, default: int | None = None) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _configure_period_fields(self) -> None:
        available_years = get_available_invoice_years(reference_date=self.today)

        self.fields["invoice_year"].choices = [
            (year, str(year)) for year in available_years
        ]

        selected_year = self._to_int(
            self._get_raw_field_value("invoice_year", self.today.year),
            self.today.year,
        )

        available_months = get_available_invoice_months(
            year=selected_year,
            reference_date=self.today,
        )

        month_labels = dict(EmployeeSimpleInvoice.Month.choices)

        self.fields["invoice_month"].choices = [
            (month, month_labels[month])
            for month in available_months
        ]

        selected_month = self._to_int(
            self._get_raw_field_value("invoice_month", self.today.month),
            self.today.month,
        )

        self._configure_day_choices(year=selected_year, month=selected_month)

        if not self.is_bound:
            self.initial.setdefault("invoice_year", self.today.year)
            self.initial.setdefault("invoice_month", self.today.month)

    def _configure_day_choices(self, *, year: int | None, month: int | None) -> None:
        try:
            max_day = calendar.monthrange(year, month)[1]
        except (TypeError, ValueError):
            max_day = 31

        if year == self.today.year and month == self.today.month:
            max_day = min(max_day, self.today.day)

        day_choices = [(day, str(day)) for day in range(1, max_day + 1)]

        self.fields["start_day"].choices = day_choices
        self.fields["end_day"].choices = day_choices

    def clean_hours(self) -> Decimal | None:
        hours = self.cleaned_data.get("hours")

        if hours is not None and hours <= 0:
            raise forms.ValidationError(_("Hours must be greater than zero."))

        return hours

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()

        invoice_year = cleaned_data.get("invoice_year")
        invoice_month = cleaned_data.get("invoice_month")
        start_day = cleaned_data.get("start_day")
        end_day = cleaned_data.get("end_day")

        if (
            invoice_year is None
            or invoice_month is None
            or start_day is None
            or end_day is None
        ):
            return cleaned_data

        if start_day > end_day:
            self.add_error("end_day", _("End day cannot be earlier than start day."))
            return cleaned_data

        try:
            start_date, end_date = build_invoice_period(
                year=invoice_year,
                month=invoice_month,
                start_day=start_day,
                end_day=end_day,
            )
        except ValidationError as exc:
            self.add_error(None, exc)
            return cleaned_data

        if end_date > self.today:
            self.add_error("end_day", _("Invoice period cannot include future dates."))
            return cleaned_data

        if self.employee is None:
            self.add_error(
                None,
                _("Employee information is required to create an invoice."),
            )
            return cleaned_data

        try:
            validate_invoice_period_available(
                employee=self.employee,
                start_date=start_date,
                end_date=end_date,
            )
        except ValidationError as exc:
            self.add_error(None, exc)

        return cleaned_data

    def clean_gst_account_number(self) -> str:
        value = self.cleaned_data.get("gst_account_number", "")

        if not value:
            return ""

        normalized = "".join(value.upper().split())

        if not re.fullmatch("\\d{9}RT\\d{4}", normalized):
            raise forms.ValidationError(
                _("Enter a valid GST/HST account number, for example 123456789 RT0001.")
            )

        return f"{normalized[:9]} {normalized[9:]}"


class EmployeeInvoiceForm(forms.Form):
    street_address = forms.CharField(max_length=50)
    city = forms.CharField(max_length=50)
    province = forms.ChoiceField(choices=CanadianProvince.choices)
    postal_code = forms.CharField(
        max_length=7,
        validators=[canadian_postal_code_validator],
    )

    def clean_street_address(self) -> str:
        street_address = self.cleaned_data.get("street_address", "")
        return street_address.strip()

    def clean_city(self) -> str:
        city = self.cleaned_data.get("city", "").strip()

        return city[:1].upper() + city[1:]

    def clean_postal_code(self) -> str:
        return normalize_canadian_postal_code(self.cleaned_data["postal_code"])
