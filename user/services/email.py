from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from user.services.tokens import build_verification_context


def send_html_email(*, subject, template_name, context, to):
    message = render_to_string(template_name, context=context)
    email = EmailMessage(
        subject=subject,
        body=message,
        to=to,
    )
    email.content_subtype = "html"
    email.send()


def send_verification_email(request, user):
    context = build_verification_context(request, user)
    send_html_email(
        subject=_("Confirm email"),
        template_name="registration/verify_user.html",
        context=context,
        to=[user.email],
    )
