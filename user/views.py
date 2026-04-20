from django.views import generic
from django.conf import settings
from django.db import transaction
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from django.contrib.auth import get_user_model, login
from django.utils.translation import gettext_lazy as _

from user import forms
from user import mixins
from user.services.rate_limits.login import (
    get_login_rate_limit_state,
    get_login_cooldown_message,
    reset_login_rate_limit,
    register_login_attempt,
)
from user.services.rate_limits.resend_verification import (
    get_resend_verification_cooldown_message,
    get_resend_verification_rate_limit_state,
    register_resend_verification_attempt,
    get_resend_verification_success_message,
)

from user.services.rate_limits.password_reset import (
    get_password_reset_state,
    register_password_reset_attempt,
    get_password_reset_cooldown_message,
)


from user.services.rate_limits.registration import (
    get_registration_cooldown_message,
    get_registration_rate_limit_state,
    register_registration_attempt,
)

from user.services.email import send_verification_email
from user.services.tokens import get_user_from_verification_data

from account.models import Profile

User = get_user_model()

PASSWORD_RESET_ATTEMPTS = settings.PASSWORD_RESET_MAX_ATTEMPTS
PASSWORD_RESET_COOLDOWN = settings.PASSWORD_RESET_COOLDOWN_SECONDS


# <-- Register -->
class UserRegistrationView(
    mixins.TurnstileMixin,
    mixins.AnonymousRequiredMixin,
    generic.CreateView,
):
    """
    1) Даем доступ к странице только неавторизованым пользователям
    2) Регистрация только сотрудников компании
    3) Перед авторизацией проходим верификацию, функция которая будет отправлять сообщение на почту
    4) Создаем пользователя с is_active = False и перенаправляем на страницу с сообщением (проверьте почту)
    5) Turnstile captcha
    6) Ограничиваем количество попыток регистраций по "ip" при невалидных данных
    """

    template_name = "registration/register.html"
    form_class = forms.UserRegistrationForm
    turnstile_error_message = _("The captcha check failed. Please try again.")

    def post(self, request, *args, **kwargs):
        state = get_registration_rate_limit_state(request)
        if state.blocked:
            self.object = None
            form = self.get_form_class()(
                request.POST or None,
                service_message=get_registration_cooldown_message(state),
            )
            return self.render_to_response(self.get_context_data(form=form))

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        if not self.is_turnstile_valid():
            state = register_registration_attempt(self.request)

            if state.blocked:
                form.service_message = get_registration_cooldown_message(state)

            return self.handle_turnstile_failure(form)

        employee = form.employee

        with transaction.atomic():
            user = form.save(commit=False)
            user.email = employee.email
            user.first_name = employee.first_name
            user.last_name = employee.last_name
            user.is_active = False
            user.save()

            employee.user = user
            employee.save(update_fields=["user"])

            Profile.objects.create(employee=employee)

            transaction.on_commit(lambda: send_verification_email(self.request, user))

        self.object = user
        return redirect("user:confirm_user")

    def form_invalid(self, form):
        self.object = None
        state = register_registration_attempt(self.request)

        if state.blocked:
            form.service_message = get_registration_cooldown_message(state)

        return self.render_to_response(self.get_context_data(form=form))


class ConfirmUser(
    mixins.TurnstileMixin,
    mixins.AnonymousRequiredMixin,
    generic.FormView,
):
    """
    1) Даем доступ к странице только неавторизованым пользователям
    2) Ограничиваем количество повторных отправок письма по полям: ["ip", "email"]
    3) Повторная отправка только если пользователь is_active=False
    4) Показываем service/success message прямо в форме
    5) Turnstile captcha
    """

    template_name = "registration/confirm_user.html"
    form_class = forms.ResendVerificationEmailForm
    turnstile_error_message = _("The captcha check failed. Please try again.")

    def form_valid(self, form):
        if not self.is_turnstile_valid():
            return self.handle_turnstile_failure(form)

        email = form.cleaned_data["email"]

        state = get_resend_verification_rate_limit_state(self.request, email)
        if state.blocked:
            form.service_message = get_resend_verification_cooldown_message(state)
            return self.render_to_response(self.get_context_data(form=form))

        state = register_resend_verification_attempt(self.request, email)
        if state.blocked:
            form.service_message = get_resend_verification_cooldown_message(state)
            return self.render_to_response(self.get_context_data(form=form))

        user = User.objects.filter(email__iexact=email, is_active=False).first()

        if user:
            send_verification_email(self.request, user)

        new_form = self.get_form_class()(
            success_message=get_resend_verification_success_message()
        )
        return self.render_to_response(self.get_context_data(form=new_form))


@transaction.atomic
def verify_user(request, uidb64, token):
    """
    1) Находим пользователя по валидному uid/token
    2) Если срок действия токена истек редиректим на invalid_verify
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

    return redirect("main:home")


class InvalidVerify(generic.TemplateView):
    template_name = "registration/invalid_verify.html"


# < -- Login -->
class LoginUser(
    mixins.TurnstileMixin,
    auth_views.LoginView,
):
    """
    1) Лимитируем попытки логина по полям: ["ip", "email"]
    2) После успешного логина сбрасываем счетчики
    3) Turnstile captcha
    """

    template_name = "registration/login.html"
    authentication_form = forms.UserAuthenticationForm
    redirect_authenticated_user = True
    turnstile_error_message = _("Please confirm that you are not a robot.")

    def post(self, request, *args, **kwargs):
        state = get_login_rate_limit_state(request)
        if state.blocked:
            form = self.authentication_form(
                request=request,
                data=request.POST or None,
                service_message=get_login_cooldown_message(state),
            )
            return self.render_to_response(self.get_context_data(form=form))

        if not self.is_turnstile_valid():
            form = self.authentication_form(request=request, data=request.POST or None)
            return self.handle_turnstile_failure(form)

        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        reset_login_rate_limit(self.request)
        return response

    def form_invalid(self, form):
        state = register_login_attempt(self.request)

        if state.blocked:
            form.service_message = get_login_cooldown_message(state)

        return self.render_to_response(self.get_context_data(form=form))


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
