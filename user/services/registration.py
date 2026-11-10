from collections.abc import Callable

from django.db import IntegrityError, transaction
from django.db.models import Value
from django.db.models.functions import Lower
from django.db.models.lookups import Exact
from django.utils.translation import gettext_lazy as _

from account.models import Employee, Profile
from user.models import User


class RegistrationConflict(Exception):
    """An expected conflict with employee eligibility or email uniqueness."""


def register_employee_user(
    *,
    employee_id: int,
    user: User,
    on_created: Callable[[User], None],
) -> User:
    """Register a prepared user atomically and schedule the supplied callback."""
    try:
        with transaction.atomic():
            employee = (
                Employee.objects.rewrite(False).select_for_update()
                .annotate(
                    _registration_email_matches=Exact(
                        Lower("email"), Lower(Value(user.email))
                    )
                )
                .filter(pk=employee_id)
                .first()
            )
            if (
                employee is None
                or not employee.is_active
                or not employee._registration_email_matches
            ):
                raise RegistrationConflict(
                    _("Registration is available only for active company employees.")
                )
            if employee.user_id is not None:
                raise RegistrationConflict(
                    _("A user with this employee email is already registered.")
                )
            if (
                User.objects.alias(_email_lower=Lower("email"))
                .filter(_email_lower=Lower(Value(employee.email)))
                .exists()
            ):
                raise RegistrationConflict(_("User with this email already exists"))

            user.email = employee.email
            user.first_name = employee.first_name_en or employee.first_name
            user.last_name = employee.last_name_en or employee.last_name
            user.is_active = False
            user.save()

            employee.user = user
            employee.save(update_fields=["user"])
            Profile.objects.create(employee=employee)

            transaction.on_commit(lambda: on_created(user))
    except IntegrityError as error:
        cause = error.__cause__
        diagnostics = getattr(cause, "diag", None)
        # psycopg2 uses pgcode; psycopg 3 uses sqlstate. Both expose diag.
        sqlstate = getattr(cause, "pgcode", None) or getattr(cause, "sqlstate", None)
        if (
            sqlstate != "23505"
            or getattr(diagnostics, "table_name", None) != User._meta.db_table
            or getattr(diagnostics, "constraint_name", None)
            not in {
                "user_email_lower_unique",
                f"{User._meta.db_table}_email_key",
            }
        ):
            raise
        raise RegistrationConflict(_("User with this email already exists")) from error

    return user
