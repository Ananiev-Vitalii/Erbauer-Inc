from django.shortcuts import render


def custom_permission_denied(request, exception):
    return render(request, "core/errors/403.html", status=403)


def custom_page_not_found(request, exception):
    return render(request, "core/errors/404.html", status=404)


def custom_server_error(request):
    return render(request, "core/errors/500.html", status=500)
