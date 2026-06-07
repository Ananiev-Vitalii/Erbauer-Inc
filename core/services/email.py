from typing import List, Optional
from dataclasses import dataclass, field

from django.core.mail import EmailMessage
from django.template.loader import render_to_string


@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    mimetype: str


@dataclass
class EmailPayload:
    subject: str
    template_name: str
    context: dict
    to: List[str]

    cc: Optional[List[str]] = field(default=None)
    bcc: Optional[List[str]] = field(default=None)
    reply_to: Optional[List[str]] = field(default=None)
    attachments: Optional[List[EmailAttachment]] = field(default=None)


def send_html_email(payload: EmailPayload) -> None:
    """
    Universal HTML email sender.
    Can be reused across all apps.
    """

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

    email.content_subtype = "html"

    if payload.attachments:
        for attachment in payload.attachments:
            email.attach(
                attachment.filename,
                attachment.content,
                attachment.mimetype,
            )

    email.send()