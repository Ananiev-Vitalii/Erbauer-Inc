from pathlib import PurePosixPath
from uuid import UUID

from account.models import Employee
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.utils.translation import override

from main.models import (
    CompanyProfile, Project, ProjectImage, Service, TeamMember,
    company_favicon_upload_path, company_logo_upload_path,
    project_cover_upload_path, project_gallery_upload_path,
    service_icon_upload_path, team_member_directory_path,
)
from main.tests.helpers import create_team_member


class UploadPathTests(SimpleTestCase):
    def test_unsaved_team_member_uses_fresh_uuid4_and_lowercase_extension(self) -> None:
        member = TeamMember(employee=Employee(email="private@example.invalid"))
        paths = [team_member_directory_path(member, "Private-Name.JPEG")
                 for _ in range(2)]
        self.assertIsNone(member.pk)
        self.assertNotEqual(*paths)
        for path in paths:
            parsed = PurePosixPath(path)
            self.assertEqual(parsed.parent.as_posix(), "team_member")
            self.assertEqual(parsed.suffix, ".jpeg")
            self.assertEqual(UUID(hex=parsed.stem).version, 4)
            self.assertNotIn("Private-Name", path)
            self.assertNotIn("private@example.invalid", path)

    def test_filename_without_extension_does_not_add_one(self) -> None:
        path = PurePosixPath(team_member_directory_path(TeamMember(), "photo"))
        self.assertEqual(path.suffix, "")
        self.assertEqual(UUID(hex=path.name).version, 4)

    def test_other_upload_paths_preserve_existing_directory_contracts(self) -> None:
        with override("en"):
            project = Project(title="My Project")
            self.assertEqual(project_cover_upload_path(project, "photo.jpg"),
                             "projects/my-project/cover/photo.jpg")
            self.assertEqual(project_gallery_upload_path(
                ProjectImage(project=project), "photo.jpg"),
                "projects/my-project/gallery/photo.jpg")
            self.assertEqual(service_icon_upload_path(Service(title_en="My Service"),
                                                     "icon.png"),
                             "services/my-service/icons/icon.png")
        self.assertEqual(company_logo_upload_path(CompanyProfile(), "logo.png"),
                         "company/logo/logo.png")
        self.assertEqual(company_favicon_upload_path(CompanyProfile(), "icon.png"),
                         "company/favicon/icon.png")

    def test_team_member_name_and_order_fallback(self) -> None:
        with override("en"):
            employee = Employee(first_name_en="First", last_name_en="Last")
            self.assertEqual(str(TeamMember(employee=employee, display_order=7)),
                             "First Last")
            employee = Employee(first_name_en="", last_name_en="",
                                first_name_uk="", last_name_uk="")
            self.assertEqual(str(TeamMember(employee=employee, display_order=7)), "7")


class TeamMemberConstraintTests(TestCase):
    def test_ordering_and_unique_display_order(self) -> None:
        later = create_team_member(1, 9)
        first = create_team_member(2, 2)
        self.assertEqual(list(TeamMember.objects.values_list("pk", flat=True)),
                         [first.pk, later.pk])
        employee = Employee.objects.create(
            first_name_en="Another", last_name_en="Employee",
            email="another@example.invalid", position=later.employee.position,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            TeamMember.objects.create(employee=employee, display_order=9)

    def test_employee_cannot_have_two_team_members(self) -> None:
        member = create_team_member()
        with self.assertRaises(IntegrityError), transaction.atomic():
            TeamMember.objects.create(employee=member.employee, display_order=2)
