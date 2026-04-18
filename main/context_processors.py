from main.services.cache import get_company_base_cached


def company_base(request) -> dict:
    return {
        "company_base": get_company_base_cached(),
    }
