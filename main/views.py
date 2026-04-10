from typing import Any
from django.views.generic import TemplateView

from main.models import CompanyProfile, Service, TeamMember, Project


class HomePageView(TemplateView):
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

        company_profile = CompanyProfile.objects.filter(is_active=True).first()
        services = list(Service.objects.all())
        projects = Project.objects.all()[:4]
        team_members = TeamMember.objects.filter(is_visible=True).select_related(
            "employee", "employee__position"
        )[:8]

        context.update(
            {
                "company_profile": company_profile,
                "service_pages": self.get_service_pages(services),
                "projects": projects,
                "team_members": team_members,
            }
        )

        return context
