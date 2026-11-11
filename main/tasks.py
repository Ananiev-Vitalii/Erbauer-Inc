from celery import shared_task
from django.utils.translation import override

from main.services.email import send_contact_email


@shared_task(ignore_result=True)
def send_contact_email_task(data: dict[str, str], language: str | None) -> None:
    with override(language):
        send_contact_email(data)
