from django.db import models
from django.db.models.functions import Lower
from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser, BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email: str | None) -> str:
        """Trim surrounding whitespace without changing the stored email case."""
        return (email or "").strip()

    def get_by_natural_key(self, username: str) -> "User":
        """Match email using the same database expression as its unique index."""
        return self.alias(_email_lower=Lower("email")).get(
            _email_lower=Lower(models.Value(username))
        )

    async def aget_by_natural_key(self, username: str) -> "User":
        """Provide the same email lookup for asynchronous authentication."""
        return await self.alias(_email_lower=Lower("email")).aget(
            _email_lower=Lower(models.Value(username))
        )

    def _create_user(self, email: str, password: str | None, **extra_fields) -> "User":
        if not email:
            raise ValueError("Email must be provided")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields,
    ) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields,
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(
        _("email"),
        unique=True,
        validators=[EmailValidator(message=_("Please enter a valid email address."))],
    )
    is_verified = models.BooleanField(_("verified"), default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(Lower("email"), name="user_email_lower_unique"),
        ]

    def __str__(self) -> str:
        return self.email
