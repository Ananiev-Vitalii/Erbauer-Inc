import calendar
import re

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from account.models import (
    CanadianProvince,
    Employee,
    EmployeeSimpleInvoice,
    Profile,
)
from account.services.simple_invoice_period import (
    build_invoice_period,
    get_available_invoice_months,
    get_available_invoice_years,
    validate_invoice_period_available,
)

User = get_user_model()


class EmployeeContactForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "phone",
            "email",
            "street_address",
            "city",
            "province",
            "postal_code",
        ]

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "")
        normalized = "".join(ch for ch in phone if ch.isdigit())

        if phone and len(normalized) != 10:
            raise forms.ValidationError(
                _("Please enter a valid " "10-digit Canadian phone number.")
            )

        if not normalized:
            return ""

        return f"({normalized[:3]}) " f"{normalized[3:6]}-" f"{normalized[6:]}"

    def clean_email(self):
        email = self.cleaned_data["email"]
        current_user = self.instance.user

        if (
            User.objects.exclude(pk=current_user.pk)
            .filter(email__iexact=email)
            .exists()
        ):
            raise forms.ValidationError(
                _("A user with this email " "is already registered.")
            )

        return email

    def clean_street_address(self):
        street_address = self.cleaned_data.get(
            "street_address",
            "",
        )
        return street_address.strip()

    def clean_city(self):
        city = self.cleaned_data.get(
            "city",
            "",
        ).strip()

        if not city:
            return ""

        return city[:1].upper() + city[1:]

    def clean_postal_code(self):
        postal_code = self.cleaned_data.get("postal_code", "").strip().upper()

        if not postal_code:
            return ""

        normalized = postal_code.replace(" ", "")

        if len(normalized) != 6:
            raise forms.ValidationError(
                _("Please enter a valid " "Canadian postal code.")
            )

        return f"{normalized[:3]} " f"{normalized[3:]}"


class EmployeePositionForm(forms.ModelForm):
    use_required_attribute = False

    class Meta:
        model = Employee
        fields = ["position"]


class ProfileAvatarForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["avatar"]

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")

        if not avatar:
            return avatar

        allowed_types = [
            "image/jpeg",
            "image/png",
            "image/webp",
        ]

        if avatar.content_type not in allowed_types:
            raise forms.ValidationError(
                _("Please upload a JPG, " "PNG, or WEBP image.")
            )

        max_size = 5 * 1024 * 1024

        if avatar.size > max_size:
            raise forms.ValidationError(_("Avatar image must be " "smaller than 5 MB."))

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
        *args,
        employee=None,
        **kwargs,
    ):
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
        field_name,
        default=None,
    ):
        if self.is_bound:
            value = self.data.get(self.add_prefix(field_name))

            if value not in (None, ""):
                return value

        value = self.initial.get(
            field_name,
            default,
        )

        if value not in (None, ""):
            return value

        return default

    @staticmethod
    def _to_int(
        value,
        default=None,
    ):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _configure_period_fields(self):
        available_years = get_available_invoice_years(
            reference_date=self.today,
        )

        self.fields["invoice_year"].choices = [
            (year, str(year)) for year in available_years
        ]

        selected_year = self._to_int(
            self._get_raw_field_value(
                "invoice_year",
                self.today.year,
            ),
            self.today.year,
        )

        available_months = get_available_invoice_months(
            year=selected_year,
            reference_date=self.today,
        )

        month_labels = dict(EmployeeSimpleInvoice.Month.choices)

        self.fields["invoice_month"].choices = [
            (
                month,
                month_labels[month],
            )
            for month in available_months
        ]

        selected_month = self._to_int(
            self._get_raw_field_value(
                "invoice_month",
                self.today.month,
            ),
            self.today.month,
        )

        self._configure_day_choices(
            year=selected_year,
            month=selected_month,
        )

        if not self.is_bound:
            self.initial.setdefault(
                "invoice_year",
                self.today.year,
            )
            self.initial.setdefault(
                "invoice_month",
                self.today.month,
            )

    def _configure_day_choices(
        self,
        *,
        year,
        month,
    ):
        try:
            max_day = calendar.monthrange(
                year,
                month,
            )[1]
        except (TypeError, ValueError):
            max_day = 31

        if year == self.today.year and month == self.today.month:
            max_day = min(
                max_day,
                self.today.day,
            )

        day_choices = [
            (day, str(day))
            for day in range(
                1,
                max_day + 1,
            )
        ]

        self.fields["start_day"].choices = day_choices
        self.fields["end_day"].choices = day_choices

    def clean_hours(self):
        hours = self.cleaned_data.get("hours")

        if hours is not None and hours <= 0:
            raise forms.ValidationError(_("Hours must be greater than zero."))

        return hours

    def clean(self):
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
            self.add_error(
                "end_day",
                _("End day cannot be earlier " "than start day."),
            )
            return cleaned_data

        try:
            start_date, end_date = build_invoice_period(
                year=invoice_year,
                month=invoice_month,
                start_day=start_day,
                end_day=end_day,
            )
        except ValidationError as exc:
            self.add_error(
                None,
                exc,
            )
            return cleaned_data

        if end_date > self.today:
            self.add_error(
                "end_day",
                _("Invoice period cannot include " "future dates."),
            )
            return cleaned_data

        if self.employee is None:
            self.add_error(
                None,
                _("Employee information is required " "to create an invoice."),
            )
            return cleaned_data

        try:
            validate_invoice_period_available(
                employee=self.employee,
                start_date=start_date,
                end_date=end_date,
            )
        except ValidationError as exc:
            self.add_error(
                None,
                exc,
            )

        return cleaned_data

    def clean_gst_account_number(self):
        value = self.cleaned_data.get(
            "gst_account_number",
            "",
        )

        if not value:
            return ""

        normalized = "".join(value.upper().split())

        if not re.fullmatch(
            r"\d{9}RT\d{4}",
            normalized,
        ):
            raise forms.ValidationError(
                _(
                    "Enter a valid GST/HST account "
                    "number, for example "
                    "123456789 RT0001."
                )
            )

        return f"{normalized[:9]} " f"{normalized[9:]}"


class EmployeeInvoiceForm(forms.Form):
    street_address = forms.CharField(max_length=50)
    city = forms.CharField(max_length=50)
    province = forms.ChoiceField(choices=CanadianProvince.choices)
    postal_code = forms.CharField(max_length=7)

    def clean_street_address(self):
        street_address = self.cleaned_data.get(
            "street_address",
            "",
        )
        return street_address.strip()

    def clean_city(self):
        city = self.cleaned_data.get(
            "city",
            "",
        ).strip()

        return city[:1].upper() + city[1:]

    def clean_postal_code(self):
        postal_code = self.cleaned_data.get("postal_code", "").strip().upper()

        normalized = postal_code.replace(
            " ",
            "",
        )

        if len(normalized) != 6:
            raise forms.ValidationError(
                _("Please enter a valid " "Canadian postal code.")
            )

        return f"{normalized[:3]} " f"{normalized[3:]}"
