import logging

from django.conf import settings
from django.db import close_old_connections
from django.utils.translation import gettext_lazy as _

from main.models import CompanyProfile
from core.services.email import EmailPayload, send_html_email


logger = logging.getLogger(__name__)


def send_contact_email(data: dict) -> None:
    company = CompanyProfile.objects.filter(is_active=True).only("name").first()

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


def send_contact_email_in_background(data: dict) -> None:
    try:
        close_old_connections()
        send_contact_email(data)

    except Exception:
        logger.exception("Failed to send contact form email.")

    finally:
        close_old_connections()