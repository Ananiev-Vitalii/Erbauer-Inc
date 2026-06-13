from typing import Any
from threading import Thread
from django.views import generic

from main.services.rate_limit import (
    get_contact_form_rate_limit_state,
    register_contact_form_attempt,
    get_contact_form_cooldown_message,
)
from main.services.email import send_contact_email_in_background
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
    template_name = "main/home.html"
    services_page_size = 6

    def get_service_pages(self, services: list[Service]) -> list[list[Service]]:
        page_size = self.services_page_size
        return [
            services[index : index + page_size]
            for index in range(0, len(services), page_size)
        ]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        services = get_homepage_services_cached()

        context.update(
            {
                "company_profile": get_homepage_company_profile_cached(),
                "service_pages": self.get_service_pages(services),
                "projects": get_homepage_projects_cached(),
                "team_members": get_homepage_team_members_cached(),
                "form": ContactForm(),
            }
        )

        return context


class ContactFormView(generic.FormView):
    form_class = ContactForm
    http_method_names = ["post"]
    template_name = "main/includes/sections/contacts.html#contact-form"

    def post(self, request, *args, **kwargs):
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

    def form_valid(self, form):
        data = form.cleaned_data.copy()

        Thread(
            target=send_contact_email_in_background,
            args=(data,),
            daemon=True,
            name="contact-form-email",
        ).start()

        new_form = self.get_form_class()()
        new_form.is_success = True

        return self.render_to_response(self.get_context_data(form=new_form))

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class ProjectDetailView(generic.DetailView):
    model = Project
    template_name = "main/project_detail.html"
    context_object_name = "project"
    queryset = Project.objects.prefetch_related("images")


class ProjectListView(generic.ListView):
    model = Project
    template_name = "main/project_list.html"
    context_object_name = "projects"
    paginate_by = 6

    @property
    def current_category(self):
        category = self.request.GET.get("category")
        return category if category in ProjectCategory.values else "all"

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.current_category != "all":
            queryset = queryset.filter(category=self.current_category)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_category"] = self.current_category
        return context
