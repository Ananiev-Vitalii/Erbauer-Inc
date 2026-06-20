from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator

DAY_CHOICES = [(day, str(day)) for day in range(1, 32)]


def profile_directory_path(instance: "Profile", filename: str) -> str:
    profile_slug = slugify(f"{instance.employee.last_name}_{instance.employee.email}")
    return f"profiles/{profile_slug}/{filename}"


class CanadianProvince(models.TextChoices):
    AB = "AB", _("Alberta")
    BC = "BC", _("British Columbia")
    MB = "MB", _("Manitoba")
    NB = "NB", _("New Brunswick")
    NL = "NL", _("Newfoundland and Labrador")
    NS = "NS", _("Nova Scotia")
    NT = "NT", _("Northwest Territories")
    NU = "NU", _("Nunavut")
    ON = "ON", _("Ontario")
    PE = "PE", _("Prince Edward Island")
    QC = "QC", _("Quebec")
    SK = "SK", _("Saskatchewan")
    YT = "YT", _("Yukon")


class Position(models.Model):
    name = models.CharField(_("Job title"), max_length=50, unique=True)

    class Meta:
        verbose_name = _("Job title")
        verbose_name_plural = _("Job titles")

    def __str__(self) -> str:
        return self.name


class Employee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee",
        verbose_name=_("User"),
        null=True,
        blank=True,
    )
    first_name = models.CharField(_("First name"), max_length=50)
    last_name = models.CharField(_("Last name"), max_length=50)
    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name=_("Job title"),
    )
    email = models.EmailField(_("Email"), unique=True)
    phone = models.CharField(_("Phone"), max_length=30, blank=True)
    street_address = models.CharField(_("Street address"), max_length=50, blank=True)
    city = models.CharField(_("City"), max_length=50, blank=True)
    province = models.CharField(
        _("Province"),
        max_length=2,
        choices=CanadianProvince.choices,
        default=CanadianProvince.BC,
    )
    postal_code = models.CharField(
        _("Postal code"),
        max_length=7,
        validators=[
            RegexValidator(
                regex=r"^[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d$",
                message=_("Enter a valid Canadian postal code."),
            ),
        ],
        blank=True,
    )
    is_active = models.BooleanField(_("Currently employed"), default=True)

    class Meta:
        verbose_name = _("Employee")
        verbose_name_plural = _("Employees")

    def save(self, *args, **kwargs) -> None:
        super().save(*args, **kwargs)

        # noinspection PyUnresolvedReferences
        if self.user_id and self.user.email != self.email:
            self.user.email = self.email
            self.user.save(update_fields=["email"])

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email


class Profile(models.Model):
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("Employee"),
    )
    avatar = models.ImageField(
        _("Avatar"),
        upload_to=profile_directory_path,
        default="profiles/default.png",
        blank=True,
    )

    class Meta:
        verbose_name = _("Profile")
        verbose_name_plural = _("Profiles")

    def __str__(self) -> str:
        return str(self.employee)


class EmployeeSimpleInvoice(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("Employee"),
    )
    invoice_number = models.PositiveIntegerField(
        _("Invoice number"),
        validators=[
            MinValueValidator(1, message=_("Enter a valid invoice number.")),
            MaxValueValidator(99, message=_("Enter a valid invoice number.")),
        ],
    )

    start_day = models.PositiveSmallIntegerField(
        _("Start day"),
        choices=DAY_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        default=1,
    )

    end_day = models.PositiveSmallIntegerField(
        _("End day"),
        choices=DAY_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        default=1,
    )

    hours = models.DecimalField(
        _("Hours"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0, message=_("Enter valid hours."))],
    )

    rate = models.DecimalField(
        _("Rate"),
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0, message=_("Enter a valid rate."))],
    )

    class Meta:
        verbose_name = _("Simple invoice")
        verbose_name_plural = _("Simple invoices")
        ordering = ["-id"]

    def __str__(self) -> str:
        return f"{self.employee.first_name} {self.employee.last_name}"


class CheatSheet(models.Model):
    name = models.CharField(_("Name"), max_length=100, unique=True)
    slug = models.SlugField(_("Slug"), max_length=120, unique=True, blank=True)

    class Meta:
        verbose_name = _("Cheat sheet")
        verbose_name_plural = _("Cheat sheets")
        ordering = ["name"]

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name