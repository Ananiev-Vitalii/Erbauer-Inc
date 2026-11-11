from django.http import HttpRequest, HttpResponse
from django.views import generic
from django.db import transaction
from django.db.models import Value
from django.db.models.functions import Lower
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views
from django.contrib.auth import get_user_model, login
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from core.mixins import RateLimitUnavailableMixin

from user import forms
from user import mixins
from user.services.rate_limits.login import (
    get_login_rate_limit_state,
    get_login_cooldown_message,
    reset_login_rate_limit,
    register_login_attempt,
    register_login_captcha_failure,
)
from user.services.rate_limits.resend_verification import (
    get_resend_verification_cooldown_message,
    get_resend_verification_rate_limit_state,
    register_resend_verification_attempt,
    register_resend_verification_captcha_failure,
    get_resend_verification_success_message,
)

from user.services.rate_limits.password_reset import (
    register_password_reset_attempt,
    register_password_reset_captcha_failure,
    get_password_reset_cooldown_message,
    get_password_reset_rate_limit_state,
)

from user.services.rate_limits.registration import (
    get_registration_cooldown_message,
    get_registration_rate_limit_state,
    register_registration_attempt,
)

from user.services.email import get_email_company_name, send_verification_email
from user.services.registration import RegistrationConflict, register_employee_user
from user.services.tokens import get_user_from_verification_data

User = get_user_model()


class UserRegistrationView(
    RateLimitUnavailableMixin,
    mixins.TurnstileMixin,
    mixins.AnonymousRequiredMixin,
    generic.CreateView,
):
    """Coordinate employee registration, CAPTCHA, and post-commit email feedback."""

    template_name = "registration/register.html"
    form_class = forms.UserRegistrationForm
    turnstile_error_message = _("The captcha check failed. Please try again.")

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        state = get_registration_rate_limit_state(request)
        if state.blocked:
            self.object = None
            form = self.get_form_class()(
                request.POST or None,
                service_message=get_registration_cooldown_message(state),
            )
            return self.render_to_response(self.get_context_data(form=form))

        return super().post(request, *args, **kwargs)

    def form_valid(self, form: forms.UserRegistrationForm) -> HttpResponse:
        """Register validated data and report email failures after commit."""
        if not self.is_turnstile_valid():
            return self.handle_turnstile_failure(form)

        user = form.save(commit=False)
        # Preserve the submitted value for the database identity recheck.
        user.email = form.cleaned_data["email"]

        def send_after_commit(created_user: User) -> None:
            if not send_verification_email(self.request, created_user):
                messages.warning(
                    self.request,
                    _(
                        "Your account has been created, but we could not "
                        "send the verification email. Please request "
                        "another verification email later."
                    ),
                )

        try:
            self.object = register_employee_user(
                employee_id=form.employee.pk, user=user, on_created=send_after_commit
            )
        except RegistrationConflict as error:
            form.add_error("email", str(error))
            return self.form_invalid(form)

        return redirect("user:confirm_user")

    def form_invalid(self, form: forms.UserRegistrationForm) -> HttpResponse:
        self.object = None
        state = register_registration_attempt(self.request)

        if state.blocked:
            form.service_message = get_registration_cooldown_message(state)

        return self.render_to_response(self.get_context_data(form=form))


class ConfirmUser(
    RateLimitUnavailableMixin,
    mixins.RateLimitedTurnstileMixin,
    mixins.AnonymousRequiredMixin,
    generic.FormView,
):
    """Resend pending-account verification with neutral responses and rate limiting."""

    template_name = "registration/confirm_user.html"
    form_class = forms.ResendVerificationEmailForm
    turnstile_error_message = _("The captcha check failed. Please try again.")

    get_email_rate_limit_state = staticmethod(get_resend_verification_rate_limit_state)
    register_email_attempt = staticmethod(register_resend_verification_attempt)
    register_captcha_failure = staticmethod(
        register_resend_verification_captcha_failure
    )
    get_email_cooldown_message = staticmethod(get_resend_verification_cooldown_message)

    def form_valid(self, form: forms.ResendVerificationEmailForm) -> HttpResponse:
        email = form.cleaned_data["email"]

        user = (
            User.objects.alias(_email_lower=Lower("email"))
            .filter(
                _email_lower=Lower(Value(email)), is_active=False, is_verified=False
            )
            .first()
        )

        if user:
            send_verification_email(self.request, user)

        new_form = self.get_form_class()(
            success_message=get_resend_verification_success_message()
        )
        return self.render_to_response(self.get_context_data(form=new_form))


@transaction.atomic
def verify_user(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    """Lock and verify a pending account, then log in only after activation."""
    user = get_user_from_verification_data(uidb64, token)

    if not user:
        return redirect("user:invalid_verify")

    if not user.is_active and not user.is_verified:
        user.is_active = True
        user.is_verified = True
        user.save(update_fields=["is_active", "is_verified"])
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")

    return redirect("main:home")


class InvalidVerify(generic.TemplateView):
    template_name = "registration/invalid_verify.html"


class LoginUser(
    RateLimitUnavailableMixin,
    mixins.TurnstileMixin,
    auth_views.LoginView,
):
    """Gate Django login with CAPTCHA and separate failure counters."""

    template_name = "registration/login.html"
    authentication_form = forms.UserAuthenticationForm
    redirect_authenticated_user = True
    turnstile_error_message = _("Please confirm that you are not a robot.")

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        state = get_login_rate_limit_state(request)
        if state.blocked:
            form = self.authentication_form(
                request=request,
                data=request.POST or None,
                service_message=get_login_cooldown_message(state),
                allow_authentication=False,
            )
            return self.render_to_response(self.get_context_data(form=form))

        captcha_valid = self.is_turnstile_valid()
        state = get_login_rate_limit_state(request)
        if state.blocked:
            form = self.authentication_form(
                request=request,
                data=request.POST or None,
                service_message=get_login_cooldown_message(state),
                allow_authentication=False,
            )
            return self.render_to_response(self.get_context_data(form=form))

        if not captcha_valid:
            state = register_login_captcha_failure(request)
            form = self.authentication_form(
                request=request,
                data=request.POST or None,
                allow_authentication=False,
                service_message=(
                    get_login_cooldown_message(state)
                    if state.blocked
                    else self.turnstile_error_message
                ),
            )
            # Render directly: form_invalid() accounts only for invalid credentials.
            return self.render_to_response(self.get_context_data(form=form))

        return super().post(request, *args, **kwargs)

    def form_valid(self, form: forms.UserAuthenticationForm) -> HttpResponse:
        reset_login_rate_limit(self.request)
        return super().form_valid(form)

    def form_invalid(self, form: forms.UserAuthenticationForm) -> HttpResponse:
        state = register_login_attempt(self.request)

        if state.blocked:
            form.service_message = get_login_cooldown_message(state)

        return self.render_to_response(self.get_context_data(form=form))


class CustomPasswordResetView(
    RateLimitUnavailableMixin,
    mixins.RateLimitedTurnstileMixin,
    mixins.AnonymousRequiredMixin,
    auth_views.PasswordResetView,
):
    """Apply CAPTCHA and rate limits before Django password reset."""

    form_class = forms.CustomPasswordResetForm
    template_name = "registration/password_reset_form.html"
    html_email_template_name = "registration/password_reset_email.html"
    success_url = reverse_lazy("user:password-reset-done")
    turnstile_error_message = _("The captcha check failed. Please try again.")

    get_email_rate_limit_state = staticmethod(get_password_reset_rate_limit_state)
    register_email_attempt = staticmethod(register_password_reset_attempt)
    register_captcha_failure = staticmethod(register_password_reset_captcha_failure)
    get_email_cooldown_message = staticmethod(get_password_reset_cooldown_message)

    def form_valid(self, form: forms.CustomPasswordResetForm) -> HttpResponse:
        self.extra_email_context = {
            "company_base": {"name": get_email_company_name()},
        }

        return super().form_valid(form)
