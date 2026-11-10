from unittest.mock import Mock

from account.models import Employee, Position
from core.services.rate_limit import RateLimitState
from user.models import User


def employee() -> Employee:
    position = Position.objects.create(name_en="Builder", name_uk="Builder")
    return Employee.objects.create(
        position=position, email="Worker@Example.invalid",
        first_name_en="Test", last_name_en="Worker",
    )


def prepared_user() -> User:
    user = User(email="worker@example.invalid")
    user.set_password("Strong-test-password-842!")
    return user


def state(blocked: bool = False) -> RateLimitState:
    return RateLimitState(blocked, 60 if blocked else 0, 1 if blocked else 0, 10)


def pg_conflict(constraint: str) -> Exception:
    error = Exception("Synthetic database error")
    error.pgcode = "23505"
    error.diag = Mock(table_name=User._meta.db_table, constraint_name=constraint)
    return error
