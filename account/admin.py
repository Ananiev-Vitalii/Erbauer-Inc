from django.contrib import admin
from modeltranslation.admin import TranslationAdmin

from account.models import Position, Employee, Profile, EmployeeSimpleInvoice
from user.admin import custom_admin_site


class PositionAdmin(TranslationAdmin):
    list_display = ("name",)


class EmployeeAdmin(TranslationAdmin):
    list_display = ("first_name", "last_name", "email", "position", "is_active")
    list_filter = ("is_active", "position")
    search_fields = ("first_name", "last_name", "email")
    fields = (
        "first_name",
        "last_name",
        "email",
        "phone",
        "position",
        "is_active",
        "street_address",
        "city",
        "province",
        "postal_code",
    )

    def delete_model(self, request, obj):
        user = obj.user
        if user:
            user.delete()
        else:
            obj.delete()

    def delete_queryset(self, request, queryset):
        for obj in queryset.select_related("user"):
            user = obj.user
            if user:
                user.delete()
            else:
                obj.delete()


class ProfileAdmin(admin.ModelAdmin):
    list_display = ("get_first_name", "get_last_name")
    search_fields = (
        "employee__first_name",
        "employee__last_name",
        "employee__email",
    )
    fields = ("get_first_name", "get_last_name", "avatar")
    readonly_fields = ("get_first_name", "get_last_name")

    @admin.display(description="First name")
    def get_first_name(self, obj):
        return obj.employee.first_name

    @admin.display(description="Last name")
    def get_last_name(self, obj):
        return obj.employee.last_name


class EmployeeSimpleInvoiceAdmin(admin.ModelAdmin):
    list_display = ("get_first_name", "get_last_name")
    search_fields = (
        "employee__first_name",
        "employee__last_name",
    )
    fields = (
        "get_first_name",
        "get_last_name",
        "employee",
        "invoice_number",
        "start_day",
        "end_day",
        "hours",
        "rate",
    )
    readonly_fields = ("get_first_name", "get_last_name")

    @admin.display(description="First name")
    def get_first_name(self, obj):
        return obj.employee.first_name

    @admin.display(description="Last name")
    def get_last_name(self, obj):
        return obj.employee.last_name


custom_admin_site.register(Position, PositionAdmin)
custom_admin_site.register(Employee, EmployeeAdmin)
custom_admin_site.register(Profile, ProfileAdmin)
custom_admin_site.register(EmployeeSimpleInvoice, EmployeeSimpleInvoiceAdmin)
