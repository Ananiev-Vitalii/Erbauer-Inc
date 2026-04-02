"""
- Общая точка входа: user:login
- Доступ к /admin/ только для пользователей с правами "is_staff", "is_active".
- Использование кастомной админки для всех моделей с украинским переводом атрибутов и activate("uk")
- При выходе из админки перенаправляет на главную
"""

from functools import update_wrapper
from django.shortcuts import redirect
from django.contrib.admin import AdminSite
from django.utils.translation import activate
from django.http import HttpResponseNotAllowed
from django.core.exceptions import PermissionDenied
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from user.models import User


class CustomAdminSite(AdminSite):
    site_header = f"Адміністрація сайту"
    site_title = "Панель адміністратора"
    index_title = "Керування сайтом"

    def has_permission(self, request):
        return (
            request.user.is_authenticated
            and request.user.is_active
            and request.user.is_staff
        )

    def logout(self, request, extra_context=None):

        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        auth_logout(request)
        return redirect("home")

    def admin_view(self, view, cacheable=False):
        wrapped_view = super().admin_view(view, cacheable=cacheable)

        def inner(request, *args, **kwargs):
            activate("uk")

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
            "Статуси",
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

    def add_view(self, request, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["title"] = "Додати користувача"
        return super().add_view(request, form_url, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["title"] = "Змінити користувача"
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["title"] = "Виберіть користувача для зміни"
        return super().changelist_view(request, extra_context=extra_context)


custom_admin_site = CustomAdminSite(name="custom_admin")
custom_admin_site.register(User, UserAdmin)
