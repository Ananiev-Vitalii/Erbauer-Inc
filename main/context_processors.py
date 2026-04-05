from .models import CompanyProfile


def company_base(request):
    return {
        "company_base": CompanyProfile.objects.filter(is_active=True)
        .only("name", "logo")
        .first()
    }
