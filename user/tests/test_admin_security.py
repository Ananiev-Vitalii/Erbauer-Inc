from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from account.models import Position
from user.admin import custom_admin_site
from user.models import User
from user.tests.helpers import state


class AdminSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.staff = User.objects.create_user(
            email="staff@example.invalid",
            password="Strong-test-password-842!",
            is_staff=True,
        )
        cls.regular = User.objects.create_user(email="employee@example.invalid")
        cls.inactive = User.objects.create_user(
            email="inactive@example.invalid", is_staff=True, is_active=False
        )
        cls.position = Position.objects.create(name_en="Builder", name_uk="Builder")

    def protected_urls(self) -> list[str]:
        return [
            reverse("custom_admin:index"),
            reverse("custom_admin:app_list", kwargs={"app_label": "account"}),
            reverse("custom_admin:autocomplete"),
            reverse("custom_admin:password_change"),
            reverse("custom_admin:password_change_done"),
            reverse("custom_admin:logout"),
            reverse("custom_admin:jsi18n"),
            reverse("custom_admin:view_on_site", args=[1, self.position.pk]),
            f"{reverse('custom_admin:index')}unknown-admin-page/",
            reverse("custom_admin:account_position_changelist"),
            reverse("custom_admin:account_position_add"),
            reverse("custom_admin:account_position_change", args=[self.position.pk]),
            reverse("custom_admin:account_position_delete", args=[self.position.pk]),
            reverse("custom_admin:account_position_history", args=[self.position.pk]),
            reverse("custom_admin:auth_user_password_change", args=[self.staff.pk]),
        ]

    def assert_shared_login_redirect(
        self, response: HttpResponse, next_url: str
    ) -> None:
        self.assertEqual(response.status_code, 302)
        location = urlsplit(response.headers["Location"])
        self.assertEqual(location.path, reverse("user:login"))
        self.assertEqual(parse_qs(location.query), {"next": [next_url]})

    def test_anonymous_admin_routes_preserve_path_and_query(self) -> None:
        for url in self.protected_urls():
            with self.subTest(url=url):
                target = f"{url}?q=two+words&next=https%3A%2F%2Foutside.invalid%2F"
                self.assert_shared_login_redirect(self.client.get(target), target)

    def test_non_staff_cannot_access_or_post_to_admin_routes(self) -> None:
        self.client.force_login(self.regular)
        for url in self.protected_urls():
            for method in ("GET", "POST", "PUT"):
                with self.subTest(url=url, method=method):
                    response = self.client.generic(method, url)
                    self.assertEqual(response.status_code, 403)

    def test_inactive_staff_is_rejected_by_site_and_view_guards(self) -> None:
        request = RequestFactory().get(reverse("custom_admin:index"))
        request.user = self.inactive
        self.assertFalse(custom_admin_site.has_permission(request))
        with patch.object(custom_admin_site, "index") as index:
            with self.assertRaises(PermissionDenied):
                custom_admin_site.admin_view(index)(request)
            index.assert_not_called()
        with self.assertRaises(PermissionDenied):
            custom_admin_site.login(request)

    def test_login_alias_redirects_get_and_rejects_other_methods(self) -> None:
        url = reverse("custom_admin:login")
        index = reverse("custom_admin:index")
        response = self.client.get(url, {"next": "https://outside.invalid/"})
        self.assert_shared_login_redirect(response, index)
        self.assertIn("no-store", response.headers["Cache-Control"])

        self.client.force_login(self.regular)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.staff)
        self.assertRedirects(self.client.get(url), index, fetch_redirect_response=False)
        self.assertEqual(self.client.get(index).status_code, 200)
        for method in ("PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
            with self.subTest(method=method):
                self.assertEqual(self.client.generic(method, url).status_code, 403)

    def test_login_alias_post_never_authenticates_with_or_without_csrf(self) -> None:
        client = Client(enforce_csrf_checks=True)
        data = {
            "username": self.staff.email,
            "password": "Strong-test-password-842!",
        }
        url = reverse("custom_admin:login")
        with patch("django.contrib.auth.forms.authenticate") as authenticate:
            self.assertEqual(client.post(url, data).status_code, 403)
            self.assertNotIn("_auth_user_id", client.session)

            client.get(reverse("user:login"))
            token = client.cookies["csrftoken"].value
            response = client.post(url, {**data, "csrfmiddlewaretoken": token})
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("_auth_user_id", client.session)
            authenticate.assert_not_called()

    def test_shared_login_returns_to_admin_and_rejects_external_next(self) -> None:
        admin_target = f"{reverse('custom_admin:index')}?section=employees"
        for target in (admin_target, "https://outside.invalid/", "//outside.invalid/"):
            with self.subTest(target=target):
                self.client.logout()
                url = f"{reverse('user:login')}?{urlencode({'next': target})}"
                with (
                    patch(
                        "user.views.get_login_rate_limit_state", return_value=state()
                    ),
                    patch(
                        "user.mixins.verify_turnstile_token",
                        return_value={"success": True},
                    ),
                    patch("user.views.reset_login_rate_limit") as reset,
                ):
                    response = self.client.post(
                        url,
                        {
                            "username": self.staff.email,
                            "password": "Strong-test-password-842!",
                        },
                    )
                expected = (
                    admin_target if target == admin_target else reverse("main:home")
                )
                self.assertRedirects(response, expected, fetch_redirect_response=False)
                self.assertEqual(
                    self.client.session["_auth_user_id"], str(self.staff.pk)
                )
                reset.assert_called_once()
                if target == admin_target:
                    self.assertEqual(self.client.get(expected).status_code, 200)

    def test_direct_model_urls_and_actions_respect_staff_permissions(self) -> None:
        self.client.force_login(self.staff)
        changelist = reverse("custom_admin:account_position_changelist")
        self.assertEqual(self.client.get(changelist).status_code, 403)

        self.staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="account", codename="view_position"
            )
        )
        self.assertEqual(self.client.get(changelist).status_code, 200)
        change = reverse(
            "custom_admin:account_position_change", args=[self.position.pk]
        )
        self.assertEqual(self.client.get(change).status_code, 200)

        for url, data in (
            (reverse("custom_admin:account_position_add"), {"name_en": "New"}),
            (change, {"name_en": "Changed", "name_uk": "Changed"}),
            (
                reverse(
                    "custom_admin:account_position_delete", args=[self.position.pk]
                ),
                {"post": "yes"},
            ),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, data).status_code, 403)

        with patch.object(
            custom_admin_site._registry[Position], "delete_queryset"
        ) as delete:
            self.client.post(
                changelist,
                {
                    "action": "delete_selected",
                    "_selected_action": [str(self.position.pk)],
                    "post": "yes",
                },
            )
            delete.assert_not_called()

        self.position.refresh_from_db()
        self.assertEqual(self.position.name_en, "Builder")
        self.assertEqual(Position.objects.count(), 1)
