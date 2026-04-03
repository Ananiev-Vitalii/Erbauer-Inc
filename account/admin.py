from django.contrib import admin

from account.models import Position, Employee, Profile


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "position", "is_active")
    list_filter = ("is_active", "position")
    search_fields = ("first_name", "last_name", "email")
    fields = ("first_name", "last_name", "email", "position", "is_active")

    def delete_model(self, request, obj) -> None:
        user = obj.user
        if user:
            user.delete()
        else:
            obj.delete()

    def delete_queryset(self, request, queryset) -> None:
        for obj in queryset.select_related("user"):
            user = obj.user
            if user:
                user.delete()
            else:
                obj.delete()


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("get_first_name", "get_last_name", "phone")
    search_fields = (
        "employee__first_name",
        "employee__last_name",
        "employee__email",
        "phone",
    )
    fields = ("get_first_name", "get_last_name", "avatar", "phone")
    readonly_fields = ("get_first_name", "get_last_name")

    @admin.display(description="First name")
    def get_first_name(self, obj):
        return obj.employee.first_name

    @admin.display(description="Last name")
    def get_last_name(self, obj):
        return obj.employee.last_name
