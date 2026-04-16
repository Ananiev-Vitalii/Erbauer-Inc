from .models import CompanyProfile


def company_base(request):
    return {
        "company_base": CompanyProfile.objects.filter(is_active=True)
        .only(
            "name",
            "favicon",
            "logo",
            "email",
            "footer_description",
            "facebook_url",
            "instagram_url",
            "telegram_url",
        )
        .first()
    }
