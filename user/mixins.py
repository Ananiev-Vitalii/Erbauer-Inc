from django.shortcuts import redirect
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from core.utils.request import get_client_ip
from user.services.turnstile import verify_turnstile_token


class AnonymousRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)


class ServiceMessageFormMixin:
    service_message = ""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["service_message"] = self.service_message
        return kwargs

    def form_invalid_with_message(self, message):
        self.service_message = message

        if not hasattr(self, "object"):
            self.object = None

        form = self.get_form()
        return self.form_invalid(form)


class TurnstileMixin:
    turnstile_context_key = "CF_TURNSTILE_SITE_KEY"
    turnstile_error_message = _("Please confirm that you are not a robot.")

    def get_context_data(self, **kwargs):
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

    def handle_turnstile_failure(self, form=None):
        if form is None:
            form = self.get_form()

        form.add_error(None, self.turnstile_error_message)
        return self.form_invalid(form)
