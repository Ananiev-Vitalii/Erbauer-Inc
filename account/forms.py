from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from account.models import (
    Employee,
    Profile,
    EmployeeSimpleInvoice,
    CanadianProvince,
)

User = get_user_model()


class EmployeeContactForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["phone", "email", "street_address", "city", "province", "postal_code"]

    def clean_phone(self):
        phone = self.cleaned_data.get("phone", "")
        normalized = "".join(ch for ch in phone if ch.isdigit())

        if phone and len(normalized) != 10:
            raise forms.ValidationError(
                _("Please enter a valid 10-digit Canadian phone number.")
            )

        if not normalized:
            return ""

        return f"({normalized[:3]}) {normalized[3:6]}-{normalized[6:]}"

    def clean_email(self):
        email = self.cleaned_data["email"].casefold()

        current_user = self.instance.user

        if (
            User.objects.exclude(pk=current_user.pk)
            .filter(email__iexact=email)
            .exists()
        ):
            raise forms.ValidationError(
                _("A user with this email is already registered.")
            )

        return email

    def clean_street_address(self):
        street_address = self.cleaned_data.get("street_address", "")
        return street_address.strip()

    def clean_city(self):
        city = self.cleaned_data.get("city", "").strip()

        if not city:
            return ""

        return city[:1].upper() + city[1:]

    def clean_postal_code(self):
        postal_code = self.cleaned_data.get("postal_code", "").strip().upper()

        if not postal_code:
            return ""

        normalized = postal_code.replace(" ", "")

        if len(normalized) != 6:
            raise forms.ValidationError(_("Please enter a valid Canadian postal code."))

        return f"{normalized[:3]} {normalized[3:]}"


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

        allowed_types = ["image/jpeg", "image/png", "image/webp"]

        if avatar.content_type not in allowed_types:
            raise forms.ValidationError(_("Please upload a JPG, PNG, or WEBP image."))

        max_size = 5 * 1024 * 1024

        if avatar.size > max_size:
            raise forms.ValidationError(_("Avatar image must be smaller than 5 MB."))

        return avatar


class SimpleInvoiceForm(forms.ModelForm):
    class Meta:
        model = EmployeeSimpleInvoice
        fields = ["invoice_number", "start_day", "end_day", "hours", "rate"]

    def clean(self):
        cleaned_data = super().clean()

        start_day = cleaned_data.get("start_day")
        end_day = cleaned_data.get("end_day")

        if start_day and end_day and start_day > end_day:
            self.add_error(
                "end_day",
                _("End day cannot be earlier than start day."),
            )

        return cleaned_data


class EmployeeInvoiceForm(forms.Form):
    street_address = forms.CharField(max_length=50)
    city = forms.CharField(max_length=50)
    province = forms.ChoiceField(choices=CanadianProvince.choices)
    postal_code = forms.CharField(max_length=7)
