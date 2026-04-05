from .models import CompanyProfile


def company_profile(request):
    return {
        "company_profile": CompanyProfile.objects.filter(is_active=True)
        .only("name", "logo")
        .first()
    }
