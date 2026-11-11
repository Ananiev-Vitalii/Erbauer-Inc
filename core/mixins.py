from typing import Any

from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.utils.translation import get_language, gettext as _

from core.services.rate_limit_redis import RateLimitUnavailable


class RateLimitUnavailableMixin:
    rate_limit_partial_template = ""

    def dispatch(
        self, request: HttpRequest, *args: Any, **kwargs: Any
    ) -> HttpResponse:
        try:
            return super().dispatch(request, *args, **kwargs)
        except RateLimitUnavailable:
            message = _(
                "This service is temporarily unavailable. Please try again later."
            )
            context = {"message": message, "language": get_language()}
            template = "core/errors/503.html"
            if self.rate_limit_partial_template:
                form = self.get_form()
                form.service_message = message
                context.update({"form": form, "csrf_token": get_token(request)})
                template = self.rate_limit_partial_template

            return HttpResponse(render_to_string(template, context), status=503)
