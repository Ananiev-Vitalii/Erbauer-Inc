from django.urls import path

from account.views import (
    CheatSheetView,
    MyProfileView,
    SimpleInvoiceCreateView,
    SimpleInvoiceDownloadView,
    SimpleInvoiceHistoryView,
    SimpleInvoicePeriodPreviewView,
    SimpleInvoiceStatusView,
    UpdateAvatarView,
    UpdateContactDetailsView,
    UpdateEmployeePositionView,
    UpdatePasswordView,
    WorkHoursUpdateView,
    WorkHoursView,
)

app_name = "account"


urlpatterns = [
    path(
        "profile-settings/",
        MyProfileView.as_view(),
        name="profile",
    ),
    path(
        "profile-settings/avatar/submit/",
        UpdateAvatarView.as_view(),
        name="update_avatar",
    ),
    path(
        "profile-settings/contact-details/submit/",
        UpdateContactDetailsView.as_view(),
        name="update_contact_details",
    ),
    path(
        "profile-settings/employee-position/submit/",
        UpdateEmployeePositionView.as_view(),
        name="update_employee_position",
    ),
    path(
        "profile-settings/update-password/submit/",
        UpdatePasswordView.as_view(),
        name="update_password",
    ),
    path(
        "work-hours/",
        WorkHoursView.as_view(),
        name="work_hours",
    ),
    path(
        "work-hours/update/",
        WorkHoursUpdateView.as_view(),
        name="work_hours_update",
    ),
    path(
        "invoice/create/",
        SimpleInvoiceCreateView.as_view(),
        name="simple_invoice_create",
    ),
    path(
        "invoice/period-preview/",
        SimpleInvoicePeriodPreviewView.as_view(),
        name="simple_invoice_period_preview",
    ),
    path(
        "invoice/<int:invoice_id>/status/",
        SimpleInvoiceStatusView.as_view(),
        name="simple_invoice_status",
    ),
    path(
        "invoice/<int:invoice_id>/download/",
        SimpleInvoiceDownloadView.as_view(),
        name="simple_invoice_download",
    ),
    path(
        "invoice/history/",
        SimpleInvoiceHistoryView.as_view(),
        name="simple_invoice_history",
    ),
    path(
        "cheat-sheets/",
        CheatSheetView.as_view(),
        name="cheat_sheets",
    ),
]
