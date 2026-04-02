from django.conf import settings
from django.urls import path, include
from django.conf.urls.static import static
from debug_toolbar.toolbar import debug_toolbar_urls

from user.admin import custom_admin_site

handler403 = "core.errors.views.custom_permission_denied"
handler404 = "core.errors.views.custom_page_not_found"
handler500 = "core.errors.views.custom_server_error"

urlpatterns = [
    path("admin/", custom_admin_site.urls),
    path("accounts/", include("user.urls", namespace="user")),
]


if settings.DEBUG:
    urlpatterns += debug_toolbar_urls()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
