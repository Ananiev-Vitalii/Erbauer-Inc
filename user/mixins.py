from collections.abc import Callable

from django.shortcuts import redirect
from django.conf import settings
from django.forms import BaseForm
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy as _

from core.utils.request import get_client_ip
from core.services.rate_limit import RateLimitState
from user.services.turnstile import verify_turnstile_token


class AnonymousRequiredMixin:
    def dispatch(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect("main:home")
        return super().dispatch(request, *args, **kwargs)


class TurnstileMixin:
    """Verify Turnstile; each view controls how failed attempts are counted."""

    turnstile_context_key = "CF_TURNSTILE_SITE_KEY"
    turnstile_error_message = _("Please confirm that you are not a robot.")

    def get_context_data(self, **kwargs) -> dict[str, object]:
        context = super().get_context_data(**kwargs)
        context[self.turnstile_context_key] = settings.CF_TURNSTILE_SITE_KEY
        return context

    def get_turnstile_token(self) -> str:
        return self.request.POST.get("cf-turnstile-response", "")

    def is_turnstile_valid(self) -> bool:
        token = self.request.POST.get("cf-turnstile-response", "")
        remote_ip = get_client_ip(self.request)
        result = verify_turnstile_token(token=token, remote_ip=remote_ip)
        self.turnstile_result = result
        return bool(result.get("success", False))

    def handle_turnstile_failure(self, form: BaseForm | None = None) -> HttpResponse:
        """Add a form error and delegate failure accounting to form_invalid()."""
        if form is None:
            form = self.get_form()

        form.add_error(None, self.turnstile_error_message)
        return self.form_invalid(form)


class RateLimitedTurnstileMixin(TurnstileMixin):
    """Check limits before Turnstile and count failed CAPTCHA separately by IP."""

    get_email_rate_limit_state: Callable[[HttpRequest, str], RateLimitState]
    register_email_attempt: Callable[[HttpRequest, str], RateLimitState]
    register_captcha_failure: Callable[[HttpRequest], RateLimitState]
    get_email_cooldown_message: Callable[[RateLimitState], str]

    def render_rate_limit_response(
        self,
        form: BaseForm,
        state: RateLimitState,
    ) -> HttpResponse:
        form.service_message = self.get_email_cooldown_message(state)
        return self.render_to_response(self.get_context_data(form=form))

    def post(
        self,
        request: HttpRequest,
        *args: object,
        **kwargs: object,
    ) -> HttpResponse:
        """Check blocking, validate input, then account for the CAPTCHA outcome."""
        state = self.get_email_rate_limit_state(request, request.POST.get("email", ""))
        form = self.get_form()
        if state.blocked:
            return self.render_rate_limit_response(form, state)

        if not form.is_valid():
            return self.form_invalid(form)

        email = form.cleaned_data["email"]
        captcha_valid = self.is_turnstile_valid()

        # Another request may have blocked this IP or email during verification.
        state = self.get_email_rate_limit_state(request, email)
        if state.blocked:
            return self.render_rate_limit_response(form, state)

        if not captcha_valid:
            state = self.register_captcha_failure(request)
            if state.blocked:
                form.service_message = self.get_email_cooldown_message(state)
            return self.handle_turnstile_failure(form)

        state = self.register_email_attempt(request, email)
        if state.blocked:
            return self.render_rate_limit_response(form, state)

        return self.form_valid(form)
