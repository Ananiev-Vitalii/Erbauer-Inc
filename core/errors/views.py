from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def custom_permission_denied(
    request: HttpRequest, exception: Exception
) -> HttpResponse:
    return render(request, "core/errors/403.html", status=403)


def custom_page_not_found(request: HttpRequest, exception: Exception) -> HttpResponse:
    return render(request, "core/errors/404.html", status=404)


def custom_server_error(request: HttpRequest) -> HttpResponse:
    return render(request, "core/errors/500.html", status=500)
