import re

from django import forms
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _, pgettext_lazy
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Layout, Field, Div

PHONE_ERROR_MESSAGE = _(
    "Enter a 10-digit Canadian or US phone number, optionally prefixed with +1 or 1."
)


class BaseStyledForm:
    def init_form_helper(self) -> None:
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_action = reverse_lazy("main:contact_submit")
        self.helper.html5_required = True
        self.helper.form_show_labels = False
        self.helper.form_show_errors = False


class ContactForm(BaseStyledForm, forms.Form):
    name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(
            attrs={
                "class": "contacts__input",
                "placeholder": _("Your Name"),
                "autocomplete": "name",
            }
        ),
    )

    phone = forms.CharField(
        max_length=17,
        error_messages={"max_length": PHONE_ERROR_MESSAGE},
        widget=forms.TextInput(
            attrs={
                "class": "contacts__input contacts__input--phone",
                "placeholder": "(234) 567-8910",
                "inputmode": "tel",
                "autocomplete": "tel-national",
                "aria-label": _("Phone number"),
            }
        ),
    )

    message = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "class": "contacts__textarea",
                "placeholder": _("Message"),
                "rows": 6,
                "autocomplete": "off",
            }
        ),
    )

    privacy_policy = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "contacts__checkbox-input",
                "required": False,
            }
        ),
        error_messages={"required": _("You must agree to the Privacy Policy.")},
    )

    def __init__(self, *args, **kwargs) -> None:
        self.service_message = kwargs.pop("service_message", "")
        super().__init__(*args, **kwargs)
        # Keep server length validation without truncating input in the browser.
        self.fields["phone"].widget.attrs.pop("maxlength", None)
        self.is_success = False
        self.init_form_helper()
        self.helper.form_class = "contacts__form"
        self.helper.form_id = "contactForm"

        privacy_acknowledge_text = _("I acknowledge the")
        privacy_policy_text = pgettext_lazy(
            "contact form checkbox link", "Privacy Policy"
        )
        privacy_policy_id = self["privacy_policy"].id_for_label
        privacy_acknowledge_id = f"{privacy_policy_id}_acknowledge"
        privacy_policy_link_id = f"{privacy_policy_id}_link"
        self.fields["privacy_policy"].widget.attrs["aria-labelledby"] = (
            f"{privacy_acknowledge_id} {privacy_policy_link_id}"
        )

        self.helper.layout = Layout(
            HTML('{% include "main/includes/forms/form_errors.html" %}'),
            Field("name"),
            Div(
                HTML('<span class="contacts__phone-prefix">+1</span>'),
                Field("phone"),
                css_class="contacts__phone-field",
            ),
            Field("message"),
            Div(
                Div(
                    Field("privacy_policy"),
                    HTML(f"""
                        <span>
                          <label for="{privacy_policy_id}"
                                 id="{privacy_acknowledge_id}">
                            {privacy_acknowledge_text}
                          </label>
                          <a href="{{% url 'main:privacy_policy' %}}"
                          target="_blank" rel="noopener noreferrer"
                          class="external-link" id="{privacy_policy_link_id}">
                            {privacy_policy_text}
                            <span class="external-icon">
                                <svg viewBox="0 0 24 24" aria-hidden="true">
                                    <path d="M14 3h7v7h-2V6.41l-9.29 9.3-1.42-1.42 9.3-9.29H14V3z"/>
                                    <path d="M5 5h6v2H7v10h10v-4h2v6H5V5z"/>
                                </svg>
                            </span>
                          </a>
                        </span>
                        """),
                    css_class="contacts__checkbox-label",
                ),
                css_class="contacts__checkbox-field",
            ),
            HTML(f"""
                <button
                    type="submit"
                    name="submit"
                    class="contacts__submit"
                >
                    {_("Send message")}
                </button>
            """),
        )

    def clean_phone(self) -> str:
        phone = self.cleaned_data["phone"]
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
