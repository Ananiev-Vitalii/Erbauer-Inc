from django.http import HttpRequest

from account.models import Profile
from main.models import CompanyProfile
from main.services.cache import get_company_base_cached


def company_base(
        request: HttpRequest,
) -> dict[str, CompanyProfile | Profile | None]:
    profile = None

    if request.user.is_authenticated:
        profile = Profile.objects.filter(employee__user=request.user).first()

    return {"company_base": get_company_base_cached(), "profile": profile}
