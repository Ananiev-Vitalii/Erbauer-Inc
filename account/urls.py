from django.urls import path

from account.views import (
    MyProfileView,
    UpdateContactDetailsView,
    UpdateEmployeePositionView,
    UpdatePasswordView,
    UpdateAvatarView,
)

app_name = "account"

urlpatterns = [
    path("profile-settings/", MyProfileView.as_view(), name="profile"),
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
]
