from datetime import date

from django.urls import path
from django.views.generic import TemplateView
from main.views import HomePageView, ContactFormView, ProjectListView, ProjectDetailView

app_name = "main"

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("contact/submit/", ContactFormView.as_view(), name="contact_submit"),
    path("projects/", ProjectListView.as_view(), name="project_list"),
    path("projects/<int:pk>/", ProjectDetailView.as_view(), name="project_detail"),
    path(
        "privacy_policy/",
        TemplateView.as_view(
            template_name="main/privacy_policy.html",
            extra_context={"privacy_policy_updated_on": date(2026, 11, 7)},
        ),
        name="privacy_policy",
    ),
]
