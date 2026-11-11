from typing import Any

from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.middleware.csrf import get_token
from django.template.loader import render_to_string
from django.utils.translation import get_language, gettext as _
from django.views import generic
from kombu.exceptions import OperationalError

from core.mixins import RateLimitUnavailableMixin

from main.services.rate_limit import (
    get_contact_form_rate_limit_state,
    register_contact_form_attempt,
    get_contact_form_cooldown_message,
)
from main.tasks import send_contact_email_task
from main.forms import ContactForm
from main.services.cache import (
    get_homepage_company_profile_cached,
    get_homepage_projects_cached,
    get_homepage_services_cached,
    get_homepage_team_members_cached,
)
from main.models import (
    Service,
    Project,
    ProjectCategory,
)


class HomePageView(generic.TemplateView):
    """Render the home page from cached public data and a fresh contact form."""

    template_name = "main/home.html"
    services_page_size = 6

    def get_service_pages(self, services: list[Service]) -> list[list[Service]]:
        page_size = self.services_page_size
        return [
            services[index: index + page_size]
            for index in range(0, len(services), page_size)
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """Load cached data, group services, and prepare team and form context."""
        context = super().get_context_data(**kwargs)
        services = get_homepage_services_cached()
        team_members = get_homepage_team_members_cached()

        context.update(
            {
                "company_profile": get_homepage_company_profile_cached(),
                "service_pages": self.get_service_pages(services),
                "projects": get_homepage_projects_cached(),
                "team_members": team_members,
                "has_more_team_members": len(team_members) > 4,
                "form": ContactForm(),
            }
        )

        return context


class ContactFormView(RateLimitUnavailableMixin, generic.FormView):
    """Rate-limit contact POSTs, validate data, and queue email delivery.

    Return HTML partials; the shared mixin handles Redis failures with HTTP 503.
    """

    form_class = ContactForm
    http_method_names = ["post"]
    template_name = "main/includes/sections/contacts.html#contact-form"
    rate_limit_partial_template = template_name

    def render_to_response(
        self, context: dict[str, Any], **response_kwargs: Any
    ) -> HttpResponse:
        """Render the partial with CSRF and response options, without processors."""
        context = {**context, "csrf_token": get_token(self.request)}
        response_kwargs.setdefault("content_type", self.content_type)
        html = render_to_string(
            self.get_template_names(), context, using=self.template_engine
        )
        return HttpResponse(html, **response_kwargs)

    def post(self, request: HttpRequest, *args, **kwargs) -> HttpResponse:
        """Check Redis blocking and count the attempt before form validation.

        Return a bound form on cooldown; otherwise continue normal processing.
        """
        state = get_contact_form_rate_limit_state(request)
        if state.blocked:
            form = self.get_form_class()(request.POST)
            form.service_message = get_contact_form_cooldown_message(state)
            return self.render_to_response(self.get_context_data(form=form))

        state = register_contact_form_attempt(request)
        if state.blocked:
            form = self.get_form_class()(request.POST)
            form.service_message = get_contact_form_cooldown_message(state)
            return self.render_to_response(self.get_context_data(form=form))

        return super().post(request, *args, **kwargs)

    def form_valid(self, form: ContactForm) -> HttpResponse:
        """Queue cleaned contact data with the active language, then reset the form.

        Keep submitted data on broker OperationalError. Success confirms queuing,
        not delivery.
        """
        data = {
            field: form.cleaned_data[field] for field in ("name", "phone", "message")
        }

        try:
            send_contact_email_task.apply_async(
                kwargs={"data": data, "language": get_language()},
                kwargsrepr="<redacted contact email arguments>",
                retry=False,
            )
        except OperationalError:
            form.service_message = _(
                "We could not submit your message. Please try again later."
            )
            return self.form_invalid(form)

        new_form = self.get_form_class()()
        new_form.is_success = True

        return self.render_to_response(self.get_context_data(form=new_form))

    def form_invalid(self, form: ContactForm) -> HttpResponse:
        return self.render_to_response(self.get_context_data(form=form))


class ProjectDetailView(generic.DetailView):
    """Render a project by primary key with prefetched images, or return 404."""

    model = Project
    template_name = "main/project_detail.html"
    context_object_name = "project"
    queryset = Project.objects.prefetch_related("images")


class ProjectListView(generic.ListView):
    """List projects by optional valid category, newest first, six per page.

    Unsupported categories show all projects; invalid pages return 404.
    """

    model = Project
    template_name = "main/project_list.html"
    context_object_name = "projects"
    paginate_by = 6

    @property
    def current_category(self) -> str:
        category = self.request.GET.get("category")
        return category if category in ProjectCategory.values else "all"

    def get_queryset(self) -> QuerySet[Project]:
        queryset = super().get_queryset()
        if self.current_category != "all":
            queryset = queryset.filter(category=self.current_category)
        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["current_category"] = self.current_category
        return context
