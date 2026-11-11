from dataclasses import dataclass, field
from typing import Any, List, Optional

from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils.functional import Promise


class EmailDeliveryError(RuntimeError):
    """The message had no recipients or the backend did not report a send."""


@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    mimetype: str


@dataclass
class EmailPayload:
    subject: str | Promise
    template_name: str
    context: dict[str, Any]
    to: List[str]

    cc: Optional[List[str]] = field(default=None)
    bcc: Optional[List[str]] = field(default=None)
    reply_to: Optional[List[str]] = field(default=None)
    attachments: Optional[List[EmailAttachment]] = field(default=None)


def send_html_email(payload: EmailPayload) -> None:
    """Render and send one HTML message, raising if no message was sent."""

    message = render_to_string(
        payload.template_name,
        context=payload.context,
    )

    email = EmailMessage(
        subject=payload.subject,
        body=message,
        to=payload.to,
        cc=payload.cc,
        bcc=payload.bcc,
        reply_to=payload.reply_to,
    )

    if not email.recipients():
        raise EmailDeliveryError("No email recipients were provided.")

    email.content_subtype = "html"

    if payload.attachments:
        for attachment in payload.attachments:
            email.attach(
                attachment.filename,
                attachment.content,
                attachment.mimetype,
            )

    if email.send() != 1:
        raise EmailDeliveryError("Email backend did not report a successful send.")
