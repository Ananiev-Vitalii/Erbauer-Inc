from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from functools import update_wrapper
from django.shortcuts import redirect
from django.contrib.admin import AdminSite
from django.http import HttpResponseNotAllowed
from django.core.exceptions import PermissionDenied
from django.contrib.auth import logout as auth_logout
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from user.models import User
from main.models import CompanyProfile


class CustomAdminSite(AdminSite):
    """Use the shared login and require active staff for administration."""

    site_header = _("Site administration")
    site_title = _("Admin Panel")
    index_title = _("Site management")

    def each_context(self, request: HttpRequest) -> dict[str, object]:
        context = super().each_context(request)
        company = CompanyProfile.objects.filter(is_active=True).first()
        context["company_base"] = company
        context["site_header"] = (
            f"{_('Site administration')} {company.name}"
            if company
            else str(_("Site administration"))
        )
        context["custom_admin_css"] = "custom_admin/css/custom_admin.css"
        return context

    def has_permission(self, request: HttpRequest) -> bool:
        return (
            request.user.is_authenticated
            and request.user.is_active
            and request.user.is_staff
        )

    def logout(
        self,
        request: HttpRequest,
        extra_context: dict[str, object] | None = None,
    ) -> HttpResponse:
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        auth_logout(request)
        return redirect("main:home")

    def admin_view(
        self,
        view: Callable[..., HttpResponse],
        cacheable: bool = False,
    ) -> Callable[..., HttpResponse]:
        wrapped_view = super().admin_view(view, cacheable=cacheable)

        def inner(request: HttpRequest, *args, **kwargs) -> HttpResponse:

            if not request.user.is_authenticated:
                return redirect("user:login")

            if not self.has_permission(request):
                raise PermissionDenied
            return wrapped_view(request, *args, **kwargs)

        return update_wrapper(inner, view)


class UserAdmin(BaseUserAdmin):
    list_display = (
        "first_name",
        "last_name",
        "email",
        "is_staff",
        "is_active",
        "is_verified",
    )
    list_filter = []
    ordering = ("id",)
    search_fields = ("email",)

    fieldsets = (
        (None, {"fields": ("first_name", "last_name", "email", "password")}),
        (
            _("Statuses"),
            {"fields": ("is_active", "is_staff", "is_superuser", "is_verified")},
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "password1",
                    "password2",
                    "is_active",
                ),
            },
        ),
    )

    def add_view(
        self,
        request: HttpRequest,
        form_url: str = "",
        extra_context: dict[str, object] | None = None,
    ) -> HttpResponse:
        extra_context = extra_context or {}
        extra_context["title"] = _("Add user")
        return super().add_view(request, form_url, extra_context=extra_context)

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, object] | None = None,
    ) -> HttpResponse:
        extra_context = extra_context or {}
        extra_context["title"] = _("Change user")
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )

    def changelist_view(
        self,
        request: HttpRequest,
        extra_context: dict[str, object] | None = None,
    ) -> HttpResponse:
        extra_context = extra_context or {}
        extra_context["title"] = _("Select user to change")
        return super().changelist_view(request, extra_context=extra_context)


custom_admin_site = CustomAdminSite(name="custom_admin")
custom_admin_site.register(User, UserAdmin)
