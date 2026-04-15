from django import forms
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Layout, Field, Submit, Div


class BaseStyledForm:
    def init_form_helper(self):
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
        max_length=14,
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

    def __init__(self, *args, **kwargs):
        self.service_message = kwargs.pop("service_message", "")
        super().__init__(*args, **kwargs)
        self.is_success = False
        self.init_form_helper()
        self.helper.form_class = "contacts__form"
        self.helper.form_id = "contactForm"

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
                          {_("I acknowledge the")}
                          <a href="{{% url 'main:privacy_policy' %}}" target="_blank" rel="noopener noreferrer" 
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
                    css_class="contacts__checkbox-label",
                ),
                css_class="contacts__checkbox-field",
            ),
            Submit(
                "submit",
                _("Send message"),
                css_class="contacts__submit",
            ),
        )

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        normalized = "".join(ch for ch in phone if ch.isdigit())

        if len(normalized) != 10:
            raise forms.ValidationError(
                _("Please enter a valid 10-digit Canadian phone number.")
            )

        return phone
