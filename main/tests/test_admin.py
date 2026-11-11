from html.parser import HTMLParser
from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.utils.safestring import SafeData

from main.admin import (
    ProjectAdmin, ProjectImageAdmin, ProjectImageInline,
    ServiceAdmin, TeamMemberAdmin,
)
from main.models import Project, ProjectImage, Service, TeamMember
from main.tests.helpers import create_project, create_team_member
from user.admin import custom_admin_site


class ImageAttributeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "img":
            self.images.append(dict(attrs))


class AdminPreviewTests(SimpleTestCase):
    def test_preview_urls_cannot_inject_attributes(self) -> None:
        unsafe_url = 'https://example.invalid/image.jpg?x=" onerror="alert(1)&y=<tag>'
        previews = (
            (ServiceAdmin(Service, custom_admin_site), "icon_preview", "icon"),
            (ProjectAdmin(Project, custom_admin_site), "cover_preview", "cover_image"),
            (ProjectImageInline(Project, custom_admin_site), "image_preview", "image"),
            (ProjectImageAdmin(ProjectImage, custom_admin_site),
             "image_preview", "image"),
        )
        for admin, method_name, field_name in previews:
            with self.subTest(preview=type(admin).__name__):
                method = getattr(admin, method_name)
                result = method(SimpleNamespace(**{
                    field_name: SimpleNamespace(url=unsafe_url)
                }))
                self.assertIsInstance(result, SafeData)
                parser = ImageAttributeParser()
                parser.feed(result)
                self.assertEqual(len(parser.images), 1)
                self.assertEqual(parser.images[0]["src"], unsafe_url)
                self.assertNotIn("onerror", parser.images[0])
                self.assertEqual(method(SimpleNamespace(**{field_name: None})), "—")


class ProjectAdminTests(TestCase):
    def test_gallery_count_is_annotated_without_per_project_queries(self) -> None:
        projects = [create_project(number) for number in range(3)]
        for number, project in enumerate(projects):
            for image_number in range(number):
                ProjectImage.objects.create(
                    project=project, image=f"projects/{number}-{image_number}.jpg"
                )
        admin = ProjectAdmin(Project, custom_admin_site)
        with self.assertNumQueries(1):
            rows = list(admin.get_queryset(RequestFactory().get("/admin/")))
        with self.assertNumQueries(0):
            self.assertEqual({row.pk: admin.images_count(row) for row in rows},
                             {project.pk: number
                              for number, project in enumerate(projects)})

    def test_team_member_initial_order_is_one_after_the_maximum(self) -> None:
        admin = TeamMemberAdmin(TeamMember, custom_admin_site)
        request = RequestFactory().get("/admin/")
        self.assertEqual(admin.get_changeform_initial_data(request),
                         {"display_order": 1})
        create_team_member(1, 3)
        create_team_member(2, 8)
        self.assertEqual(admin.get_changeform_initial_data(request),
                         {"display_order": 9})
