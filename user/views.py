from django.views import generic
from django.conf import settings
from django.db import transaction
from django.contrib import messages
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from django.contrib.auth import get_user_model, login
from django.utils.translation import gettext_lazy as _

from user import forms
from user import mixins
from user.services.rate_limits.resend_verification import (
    get_resend_verification_cooldown_message,
    get_resend_verification_state,
    register_resend_verification_attempt,
)

from user.services.rate_limits.password_reset import (
    get_password_reset_state,
    register_password_reset_attempt,
    get_password_reset_cooldown_message,
)

from .services.login_lockout import (
    clear_login_email,
    full_reset_lockout_state,
    get_lockout_data,
    remember_login_email,
    start_fixed_lockout,
    is_locked_after_failed_login,
)

from user.services.registration_rate_limit import (
    is_blocked,
    registration_attempt,
    cooldown_message,
)
from user.services.email import send_verification_email
from user.services.tokens import get_user_from_verification_data

User = get_user_model()

PASSWORD_RESET_ATTEMPTS = settings.PASSWORD_RESET_MAX_ATTEMPTS
PASSWORD_RESET_COOLDOWN = settings.PASSWORD_RESET_COOLDOWN_SECONDS
VERIFICATION_COOLDOWN = settings.RESEND_VERIFICATION_COOLDOWN_SECONDS
VERIFICATION_ATTEMPTS = settings.RESEND_VERIFICATION_MAX_ATTEMPTS
REGISTRATION_ATTEMPTS = settings.REGISTRATION_ATTEMPTS_LIMIT
REGISTRATION_COOLDOWN = settings.REGISTRATION_COOLDOWN_SECONDS


# <-- Register -->
class UserRegistrationView(
    mixins.ServiceMessageFormMixin,
    mixins.TurnstileMixin,
    mixins.AnonymousRequiredMixin,
    generic.CreateView,
):
    """
    1) Даем доступ к странице только неавторизованым пользователям
    2) Перед авторизацией проходим верификацию, функция которая будет отправлять сообщение на почту
    3) Создаем пользователя с is_active = False и перенаправляем на страницу с сообщением (проверьте почту)
    4) Turnstile captcha
    5) Ограничиваем количество регистраций по "ip"
    """

    template_name = "registration/register.html"
    form_class = forms.UserRegistrationForm
    turnstile_error_message = _("The captcha check failed. Please try again.")

    def post(self, request, *args, **kwargs):
        blocked, remaining_minutes = is_blocked(request)
        if blocked:
            return self.form_invalid_with_message(cooldown_message(remaining_minutes))
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        if not self.is_turnstile_valid():
            return self.handle_turnstile_failure(form)

        registration_attempt(
            request=self.request,
            attempts_limit=REGISTRATION_ATTEMPTS,
            cooldown_seconds=REGISTRATION_COOLDOWN,
        )

        with transaction.atomic():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            transaction.on_commit(lambda: send_verification_email(self.request, user))

        self.object = user
        return redirect("user:confirm_user")


class ConfirmUser(
    mixins.ServiceMessageFormMixin,
    mixins.TurnstileMixin,
    mixins.AnonymousRequiredMixin,
    generic.FormView,
):
    """
    1) Даем доступ к странице только неавторизованым пользователям
    2) Ограничиваем количество повторных отправок письма по полям: ["ip", "email"]
    3) Повторная отправка только если пользователь is_active=False
    4) Используем messages в шаблонах для уведомлений
    5) Turnstile captcha
    """

    template_name = "registration/confirm_user.html"
    form_class = forms.ResendVerificationEmailForm
    turnstile_error_message = _("The captcha check failed. Please try again.")

    def form_valid(self, form):
        if not self.is_turnstile_valid():
            return self.handle_turnstile_failure(form)

        email = form.cleaned_data["email"]
        state = get_resend_verification_state(self.request, email)

        if state["remaining_minutes"] > 0:
            return self.form_invalid_with_message(
                get_resend_verification_cooldown_message(state["remaining_minutes"])
            )

        user = User.objects.filter(email__iexact=email, is_active=False).first()

        register_resend_verification_attempt(
            request=self.request,
            email=email,
            attempts_limit=VERIFICATION_ATTEMPTS,
            cooldown_seconds=VERIFICATION_COOLDOWN,
        )

        if user:
            send_verification_email(self.request, user)

        messages.success(
            self.request,
            _(
                "If this email address is associated with an unverified account, "
                "we have sent a new verification email."
            ),
        )
        return redirect("user:confirm_user")


@transaction.atomic
def verify_user(request, uidb64, token):
    """
    1) Находим пользователя по валидному uid/token
    2) Если срок действия токена истек редиректим
    3) Активируем и верифицируем пользователя
    4) Логиним в систему и отправляем на главную
    """
    user = get_user_from_verification_data(uidb64, token)

    if not user:
        return redirect("user:invalid_verify")

    if not user.is_active:
        user.is_active = True
        user.is_verified = True
        user.save(update_fields=["is_active", "is_verified"])
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    return redirect("home")


class InvalidVerify(generic.TemplateView):
    template_name = "registration/invalid_verify.html"


# < -- Login -->
class LoginUser(
    mixins.ServiceMessageFormMixin, mixins.TurnstileMixin, auth_views.LoginView
):
    """
    Django login + CustomForm + Django axes + Turnstile captcha

    Логика Django axes:
    1) Блокировка срабатывает после 3 ошибок:
       - либо по одному IP
       - либо по одному username
    2) После успешного логина сбрасываются обе оси:
       - username
       - ip
    3) После истечения таймаута также сбрасываются обе оси:
       - username
       - ip
    4) Во время блокировки запросы не выполняются
    """

    template_name = "registration/login.html"
    authentication_form = forms.UserAuthenticationForm
    turnstile_error_message = _("Please confirm that you are not a robot.")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["service_message"] = get_lockout_data(self.request)["message"]
        return kwargs

    def _handle_successful_login(self, request, response):
        full_reset_lockout_state(request)
        clear_login_email(request)
        return response

    def _handle_failed_login(self, request, response):
        if not is_locked_after_failed_login(request):
            return response

        start_fixed_lockout(request)
        lockout = get_lockout_data(request)
        return self.form_invalid_with_message(lockout["message"])

    def post(self, request, *args, **kwargs):
        remember_login_email(request)

        lockout = get_lockout_data(request)
        if lockout["is_locked"]:
            return self.form_invalid_with_message(lockout["message"])

        if not self.is_turnstile_valid():
            return self.handle_turnstile_failure()

        response = super().post(request, *args, **kwargs)

        if request.user.is_authenticated:
            return self._handle_successful_login(request, response)

        return self._handle_failed_login(request, response)


# <-- Password reset -->
class CustomPasswordResetView(
    mixins.ServiceMessageFormMixin,
    mixins.TurnstileMixin,
    mixins.AnonymousRequiredMixin,
    auth_views.PasswordResetView,
):
    """
    1) Доступ только анонимным пользователям
    2) Turnstile captcha
    3) Стандартный Django password reset flow
    4) Ограничение количества попыток по IP и email
    """

    form_class = forms.CustomPasswordResetForm
    template_name = "registration/password_reset_form.html"
    success_url = reverse_lazy("user:password-reset-done")
    turnstile_error_message = _("The captcha check failed. Please try again.")

    def form_valid(self, form):
        if not self.is_turnstile_valid():
            return self.handle_turnstile_failure(form)

        email = form.cleaned_data["email"]
        state = get_password_reset_state(self.request, email)

        if state["remaining_minutes"] > 0:
            return self.form_invalid_with_message(
                get_password_reset_cooldown_message(state["remaining_minutes"])
            )

        register_password_reset_attempt(
            request=self.request,
            email=email,
            attempts_limit=PASSWORD_RESET_ATTEMPTS,
            cooldown_seconds=PASSWORD_RESET_COOLDOWN,
        )

        return super().form_valid(form)
