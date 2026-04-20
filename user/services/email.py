from django.utils.translation import gettext_lazy as _

from core.services.email import EmailPayload, send_html_email
from user.services.tokens import build_verification_context


def send_verification_email(request, user) -> None:
    context = build_verification_context(request, user)

    payload = EmailPayload(
        subject=_("Confirm email"),
        template_name="registration/verify_user.html",
        context=context,
        to=[user.email],
    )

    send_html_email(payload)
