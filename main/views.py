from django.views.generic import TemplateView

from main.models import CompanyProfile, TeamMember


class HomePageView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["company_profile"] = CompanyProfile.objects.filter(
            is_active=True
        ).first()
        context["team_members"] = TeamMember.objects.filter(is_visible=True)
        # context["projects"] = Project.objects.filter(is_published=True)[:6]

        return context
