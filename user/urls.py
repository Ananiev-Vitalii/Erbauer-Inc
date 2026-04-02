from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from user.views import (
    UserRegistrationView,
    verify_user,
    InvalidVerify,
    ConfirmUser,
    LoginUser,
    CustomPasswordResetView,
)

from user.forms import CustomSetPasswordForm

app_name = "user"

urlpatterns = [
    # Registration / log in / log out
    path("register/", UserRegistrationView.as_view(), name="register"),
    path("verify/<uidb64>/<token>/", verify_user, name="verify_user"),
    path("verify/invalid/", InvalidVerify.as_view(), name="invalid_verify"),
    path("confirm_user/", ConfirmUser.as_view(), name="confirm_user"),
    path("login/", LoginUser.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="home"), name="logout"),
    # Registration / password reset
    path("password_reset/", CustomPasswordResetView.as_view(), name="password-reset"),
    path(
        "password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(),
        name="password-reset-done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            form_class=CustomSetPasswordForm,
            success_url=reverse_lazy("user:password-reset-complete"),
        ),
        name="password-reset-confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(),
        name="password-reset-complete",
    ),
]
