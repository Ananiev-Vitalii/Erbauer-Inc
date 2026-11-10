from django.http import HttpRequest
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Invalidate pending-account tokens when verification state or email changes."""

    def _make_hash_value(self, user: User, timestamp: int) -> str:
        email = getattr(user, user.get_email_field_name(), "") or ""
        return f"{user.pk}{user.is_verified}{timestamp}{email}"


token_generator = EmailVerificationTokenGenerator()


def build_verification_context(
    request: HttpRequest,
    user: User,
) -> dict[str, User | str]:
    current_site = get_current_site(request)

    return {
        "user": user,
        "domain": current_site.domain,
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": token_generator.make_token(user),
        "protocol": "https" if request.is_secure() else "http",
    }


def get_user_from_verification_data(uidb64: str, token: str) -> "User | None":
    """Lock the user and check the token inside the caller's atomic transaction."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.select_for_update().get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None

    if token_generator.check_token(user, token):
        return user

    return None
