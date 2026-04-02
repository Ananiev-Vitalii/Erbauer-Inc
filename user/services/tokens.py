from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """
    Проверяет не только срок годности и валидность токена а еще и поле 'is_verified'
    для того чтобы иметь возможность отправлять письма не is_verified пользователям повторно,
    если пользователь is_verified все отправленные ссылки на почте невалидны.
    """

    def _make_hash_value(self, user, timestamp):
        email = getattr(user, user.get_email_field_name(), "") or ""
        return f"{user.pk}{user.is_verified}{timestamp}{email}"


token_generator = EmailVerificationTokenGenerator()


def build_verification_context(request, user):
    current_site = get_current_site(request)

    return {
        "config": user,
        "domain": current_site.domain,
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": token_generator.make_token(user),
        "protocol": "https" if request.is_secure() else "http",
    }


def get_user_from_verification_data(uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None

    if token_generator.check_token(user, token):
        return user

    return None
