from django.conf import settings
from django.urls import path, include
from django.conf.urls.static import static
from django.conf.urls.i18n import set_language

from user.admin import custom_admin_site

handler403 = "core.errors.views.custom_permission_denied"
handler404 = "core.errors.views.custom_page_not_found"
handler500 = "core.errors.views.custom_server_error"

urlpatterns = [
    path("i18n/setlang/", set_language, name="set_language"),
    path("", include("main.urls", namespace="main")),
    path("admin/", custom_admin_site.urls),
    path("accounts/", include("user.urls", namespace="user")),
    path("profiles/", include("account.urls", namespace="account")),
]


if settings.DEBUG:
    from debug_toolbar.toolbar import debug_toolbar_urls


    urlpatterns += debug_toolbar_urls()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
