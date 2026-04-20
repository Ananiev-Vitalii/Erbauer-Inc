from django import forms
from crispy_forms.helper import FormHelper
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from django.contrib.auth import forms as auth_forms
from crispy_forms.layout import HTML, Layout, Field, Submit, Div

from account.models import Employee

User = get_user_model()


class BaseStyledForm:
    turnstile_submit_css_id = "form-submit-btn"
    submit_css_class = "base_submit_btn"

    def init_form_helper(self):
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "base-form"
        self.helper.html5_required = True
        self.helper.form_show_labels = False
        self.helper.form_show_errors = False

    def style_fields(self):
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                continue

            existing_classes = field.widget.attrs.get("class", "").strip()
            classes = f"{existing_classes} form-control".strip()

            field.widget.attrs.update(
                {
                    "class": classes,
                    "placeholder": f"{field.label}",
                }
            )

    def get_turnstile_html(self, extra_classes="mt-3"):
        classes = f"cf-turnstile {extra_classes}".strip()
        return HTML(f"""
            <div
                class="{classes}"
                data-theme="auto"
                data-size="flexible"
                data-sitekey="{{{{ CF_TURNSTILE_SITE_KEY }}}}"
                data-callback="turnstileSuccess"
                data-expired-callback="turnstileExpired"
                data-language="{{{{ LANGUAGE_CODE|slice:':2' }}}}"
            ></div>
            """)

    def get_turnstile_submit(self, name="submit", value="Submit", css_class=None):
        return Submit(
            name,
            value,
            css_id=self.turnstile_submit_css_id,
            css_class=css_class or self.submit_css_class,
            disabled=True,
        )


class UserRegistrationForm(BaseStyledForm, auth_forms.UserCreationForm):
    employee: Employee | None = None

    privacy_policy = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "user-checkbox-input",
                "required": False,
            }
        ),
        error_messages={"required": _("You must agree to the Privacy Policy.")},
    )

    class Meta:
        model = User
        fields = ["email", "password1", "password2", "privacy_policy"]

    def __init__(self, *args, **kwargs):
        self.service_message = kwargs.pop("service_message", "")
        super().__init__(*args, **kwargs)
        self.init_form_helper()
        self.style_fields()
        self.fields["password1"].help_text = ""
        self.fields["password2"].help_text = ""

        self.helper.layout = Layout(
            HTML(
                '{% include "user/forms/includes/form_errors.html" with error_mode="default" %}'
            ),
            Field("email"),
            Field("password1", template="user/forms/fields/password.html"),
            Field("password2", template="user/forms/fields/password.html"),
            Div(
                Div(
                    Field("privacy_policy"),
                    HTML(f"""
                        <span>
                          {_("I acknowledge the")}
                          <a href="{{% url 'main:privacy_policy' %}}"
                             target="_blank"
                             rel="noopener noreferrer"
                             class="external-link">
                            {_("Privacy Policy")}
                            <span class="external-icon">
                              <svg viewBox="0 0 24 24" aria-hidden="true">
                                <path d="M14 3h7v7h-2V6.41l-9.29 9.3-1.42-1.42 9.3-9.29H14V3z"/>
                                <path d="M5 5h6v2H7v10h10v-4h2v6H5V5z"/>
                              </svg>
                            </span>
                          </a>
                        </span>
                        """),
                    css_class="user-checkbox-label",
                ),
                css_class="user-checkbox-field",
            ),
            self.get_turnstile_html(),
            self.get_turnstile_submit(value=_("Register")),
        )

    def clean_email(self):
        email = self.cleaned_data["email"].casefold()
        employee = Employee.objects.filter(email__iexact=email, is_active=True).first()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("User with this email already exists"))

        if not employee:
            raise forms.ValidationError(
                _("Registration is available only for active company employees.")
            )

        if employee.user is not None:
            raise forms.ValidationError(
                _("A user with this employee email is already registered.")
            )

        self.employee = employee
        return email


class ResendVerificationEmailForm(BaseStyledForm, forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": _("Email"),
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.service_message = kwargs.pop("service_message", "")
        super().__init__(*args, **kwargs)
        self.init_form_helper()
        self.helper.layout = Layout(
            HTML(
                '{% include "forms/includes/form_errors.html" with error_mode="default" %}'
            ),
            Field("email"),
            self.get_turnstile_html(),
            self.get_turnstile_submit(value=_("Resend verification email")),
        )

    def clean_email(self):
        return self.cleaned_data["email"].casefold()


class UserAuthenticationForm(BaseStyledForm, auth_forms.AuthenticationForm):
    def __init__(self, *args, **kwargs):
        self.service_message = kwargs.pop("service_message", "")
        super().__init__(*args, **kwargs)
        self.init_form_helper()
        self.style_fields()

        self.helper.layout = Layout(
            HTML(
                '{% include "user/forms/includes/form_errors.html" with error_mode="login" %}'
            ),
            Field("username"),
            Field("password", template="user/forms/fields/password.html"),
            self.get_turnstile_html(),
            self.get_turnstile_submit(value=_("Log in")),
        )


class CustomPasswordResetForm(BaseStyledForm, auth_forms.PasswordResetForm):
    def __init__(self, *args, **kwargs):
        self.service_message = kwargs.pop("service_message", "")
        super().__init__(*args, **kwargs)
        self.init_form_helper()
        self.style_fields()

        self.helper.layout = Layout(
            HTML(
                '{% include "forms/includes/form_errors.html" with error_mode="default" %}'
            ),
            Field("email"),
            self.get_turnstile_html(),
            self.get_turnstile_submit(value=_("Send an email")),
        )

    def clean_email(self):
        return self.cleaned_data["email"].casefold()


class CustomSetPasswordForm(BaseStyledForm, auth_forms.SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_form_helper()
        self.style_fields()

        self.fields["new_password1"].help_text = ""
        self.fields["new_password2"].help_text = ""

        self.helper.layout = Layout(
            HTML(
                '{% include "forms/includes/form_errors.html" with error_mode="default" %}'
            ),
            Field("new_password1", template="forms/fields/password.html"),
            Field("new_password2", template="forms/fields/password.html"),
            Submit(
                "submit",
                "Change Password",
                css_class="btn btn-primary text-white btn-lg w-100 mt-4",
            ),
        )
