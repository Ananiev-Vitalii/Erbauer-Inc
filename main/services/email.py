from django.conf import settings
from django.utils.translation import gettext_lazy as _

from main.models import CompanyProfile
from core.services.email import EmailPayload, send_html_email


def send_contact_email(data: dict) -> None:
    company = CompanyProfile.objects.filter(is_active=True).only("name", "logo").first()

    context = {
        **data,
        "company_base": company,
    }

    payload = EmailPayload(
        subject=_("New Contact Request"),
        template_name="main/contact_email.html",
        context=context,
        to=[settings.COMPANY_CONTACT_EMAIL],
    )

    send_html_email(payload)
