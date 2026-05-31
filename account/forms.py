from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from account.models import Employee, Position, Profile

User = get_user_model()


class EmployeeContactForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["phone", "email"]

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


class EmployeePositionForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = ["position"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["position"].queryset = Position.objects.order_by("name")
        self.fields["position"].empty_label = None


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
