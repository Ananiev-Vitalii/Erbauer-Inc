import logging
from email.utils import parseaddr

from anymail.exceptions import AnymailAPIError, AnymailRecipientsRefused
from requests.exceptions import RequestException
from django.conf import settings
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from core.services.email import EmailPayload, send_html_email
from user.services.tokens import build_verification_context
from user.models import User
from main.models import CompanyProfile

logger = logging.getLogger(__name__)


def get_email_company_name() -> str:
    """Use active branding, or the configured sender's name/address if absent."""
    try:
        return CompanyProfile.objects.values_list("name", flat=True).get(is_active=True)
    except CompanyProfile.DoesNotExist:
        display_name, address = parseaddr(settings.DEFAULT_FROM_EMAIL or "")
        return display_name or address


def send_verification_email(request: HttpRequest, user: User) -> bool:
    """Send verification mail; log expected delivery failures and return False."""
    context = build_verification_context(request, user)
    context["company_base"] = {"name": get_email_company_name()}

    payload = EmailPayload(
        subject=_("Confirm email"),
        template_name="registration/verify_user.html",
        context=context,
        to=[user.email],
    )

    try:
        send_html_email(payload)
    except (AnymailAPIError, AnymailRecipientsRefused, RequestException):
        logger.exception("Verification email delivery failed.")
        return False
    return True
