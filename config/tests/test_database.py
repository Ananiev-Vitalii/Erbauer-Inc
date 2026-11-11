from django.contrib.auth.models import Group
from django.db import connection
from django.test import TestCase


class DatabaseIsolationTests(TestCase):
    def test_uses_isolated_database(self) -> None:
        self.assertEqual(connection.settings_dict["HOST"], "127.0.0.1")
        self.assertEqual(str(connection.settings_dict["PORT"]), "55432")

        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user")
            database_name, database_user = cursor.fetchone()

        self.assertEqual(database_name, "test_erbauer_backend")
        self.assertEqual(database_user, "erbauer_test")

        group = Group.objects.create(name="database-isolation-check")
        saved_group = Group.objects.get(pk=group.pk)
        self.assertEqual(saved_group.name, "database-isolation-check")
