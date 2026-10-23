import calendar
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from account.storage import PrivateInvoiceCloudinaryStorage

DAY_CHOICES = [(day, str(day)) for day in range(1, 32)]

WORK_HOURS_STEP = Decimal("0.10")


def current_invoice_year() -> int:
    return timezone.localdate().year


def current_invoice_month() -> int:
    return timezone.localdate().month


def simple_invoice_pdf_path(
    instance: "EmployeeSimpleInvoice",
    filename: str,
) -> str:
    return (
        f"invoices/employee-{instance.employee_id}/" f"invoice-{instance.id}/{filename}"
    )


def cheatsheet_step_image_path(
    instance: "CheatSheetStep",
    filename: str,
) -> str:
    cheatsheet_slug = slugify(instance.cheatsheet.name)

    return (
        f"cheatsheets/"
        f"{cheatsheet_slug}/"
        f"step-{instance.step_number}/"
        f"{filename}"
    )


def profile_directory_path(
    instance: "Profile",
    filename: str,
) -> str:
    profile_slug = slugify(
        f"{instance.employee.last_name}_" f"{instance.employee.email}"
    )

    return f"profiles/" f"{profile_slug}/" f"{filename}"


class CanadianProvince(models.TextChoices):
    AB = "AB", _("Alberta")
    BC = "BC", _("British Columbia")
    MB = "MB", _("Manitoba")
    NB = "NB", _("New Brunswick")
    NL = (
        "NL",
        _("Newfoundland and Labrador"),
    )
    NS = "NS", _("Nova Scotia")
    NT = (
        "NT",
        _("Northwest Territories"),
    )
    NU = "NU", _("Nunavut")
    ON = "ON", _("Ontario")
    PE = (
        "PE",
        _("Prince Edward Island"),
    )
    QC = "QC", _("Quebec")
    SK = "SK", _("Saskatchewan")
    YT = "YT", _("Yukon")


class Position(models.Model):
    name = models.CharField(
        _("Job title"),
        max_length=50,
        unique=True,
    )

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

    first_name = models.CharField(
        _("First name"),
        max_length=50,
    )

    last_name = models.CharField(
        _("Last name"),
        max_length=50,
    )

    position = models.ForeignKey(
        Position,
        on_delete=models.PROTECT,
        related_name="employees",
        verbose_name=_("Job title"),
    )

    email = models.EmailField(
        _("Email"),
        unique=True,
    )

    phone = models.CharField(
        _("Phone"),
        max_length=30,
        blank=True,
    )

    street_address = models.CharField(
        _("Street address"),
        max_length=50,
        blank=True,
    )

    city = models.CharField(
        _("City"),
        max_length=50,
        blank=True,
    )

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
                regex=(r"^[A-Za-z]\d[A-Za-z]" r"[ -]?\d[A-Za-z]\d$"),
                message=_("Enter a valid Canadian " "postal code."),
            ),
        ],
        blank=True,
    )

    is_active = models.BooleanField(
        _("Currently employed"),
        default=True,
    )

    class Meta:
        verbose_name = _("Employee")
        verbose_name_plural = _("Employees")

    def save(
        self,
        *args,
        **kwargs,
    ) -> None:
        super().save(
            *args,
            **kwargs,
        )

        # noinspection PyUnresolvedReferences
        if self.user_id and self.user.email != self.email:
            self.user.email = self.email

            self.user.save(update_fields=["email"])

    def __str__(self) -> str:
        return (f"{self.first_name} " f"{self.last_name}").strip() or self.email


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
    class Status(models.TextChoices):
        PROCESSING = (
            "processing",
            _("Processing"),
        )
        SENT = (
            "sent",
            _("Sent"),
        )
        FAILED = (
            "failed",
            _("Failed"),
        )

    class Month(models.IntegerChoices):
        JANUARY = 1, _("January")
        FEBRUARY = 2, _("February")
        MARCH = 3, _("March")
        APRIL = 4, _("April")
        MAY = 5, _("May")
        JUNE = 6, _("June")
        JULY = 7, _("July")
        AUGUST = 8, _("August")
        SEPTEMBER = 9, _("September")
        OCTOBER = 10, _("October")
        NOVEMBER = 11, _("November")
        DECEMBER = 12, _("December")

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("Employee"),
    )

    invoice_number = models.PositiveIntegerField(
        _("Invoice number"),
        validators=[
            MinValueValidator(
                1,
                message=_("Enter a valid " "invoice number."),
            ),
            MaxValueValidator(
                99,
                message=_("Enter a valid " "invoice number."),
            ),
        ],
    )

    invoice_year = models.PositiveSmallIntegerField(
        _("Invoice year"),
        default=current_invoice_year,
        validators=[
            MinValueValidator(
                2000,
                message=_("Enter a valid " "invoice year."),
            ),
            MaxValueValidator(
                2100,
                message=_("Enter a valid " "invoice year."),
            ),
        ],
    )

    invoice_month = models.PositiveSmallIntegerField(
        _("Invoice month"),
        choices=Month.choices,
        default=current_invoice_month,
    )

    start_day = models.PositiveSmallIntegerField(
        _("Start day"),
        choices=DAY_CHOICES,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(31),
        ],
        default=1,
    )

    end_day = models.PositiveSmallIntegerField(
        _("End day"),
        choices=DAY_CHOICES,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(31),
        ],
        default=1,
    )

    hours = models.DecimalField(
        _("Hours"),
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(
                0,
                message=_("Enter valid hours."),
            ),
        ],
    )

    rate = models.DecimalField(
        _("Rate"),
        max_digits=8,
        decimal_places=2,
        validators=[
            MinValueValidator(
                0,
                message=_("Enter a valid rate."),
            ),
        ],
    )

    gst_account_number = models.CharField(
        _("GST/HST Account Number"),
        max_length=17,
        blank=True,
        default="",
    )

    gst = models.DecimalField(
        _("GST"),
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(
                0,
                message=_("Enter a valid GST " "percentage."),
            ),
            MaxValueValidator(
                100,
                message=_("GST percentage cannot " "exceed 100."),
            ),
        ],
        default=5,
    )

    wsbc = models.DecimalField(
        _("WCB"),
        max_digits=5,
        decimal_places=2,
        validators=[
            MinValueValidator(
                0,
                message=_("Enter a valid WSBC " "percentage."),
            ),
            MaxValueValidator(
                100,
                message=_("WSBC percentage cannot " "exceed 100."),
            ),
        ],
        default=0,
    )

    pdf_file = models.FileField(
        _("PDF file"),
        upload_to=(simple_invoice_pdf_path),
        storage=(PrivateInvoiceCloudinaryStorage()),
        blank=True,
    )

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=Status.choices,
        default=Status.PROCESSING,
    )

    created_at = models.DateTimeField(
        _("Created at"),
        auto_now_add=True,
    )

    class Meta:
        verbose_name = _("Simple invoice")
        verbose_name_plural = _("Simple invoices")
        ordering = ["-id"]

    def clean(self) -> None:
        super().clean()

        errors = {}

        if self.invoice_year is not None and self.invoice_month is not None:
            max_day = calendar.monthrange(
                self.invoice_year,
                self.invoice_month,
            )[1]

            if self.start_day is not None and self.start_day > max_day:
                errors["start_day"] = _(
                    "The selected start day " "does not exist in the " "selected month."
                )

            if self.end_day is not None and self.end_day > max_day:
                errors["end_day"] = _(
                    "The selected end day " "does not exist in the " "selected month."
                )

        if (
            self.start_day is not None
            and self.end_day is not None
            and self.start_day > self.end_day
        ):
            errors["end_day"] = _("End day cannot be earlier " "than start day.")

        if errors:
            raise ValidationError(errors)

    @property
    def period_start(self) -> date:
        return date(
            self.invoice_year,
            self.invoice_month,
            self.start_day,
        )

    @property
    def period_end(self) -> date:
        return date(
            self.invoice_year,
            self.invoice_month,
            self.end_day,
        )

    def __str__(self) -> str:
        return f"{self.employee.first_name} " f"{self.employee.last_name}"


class EmployeeWorkHours(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="work_hours",
        verbose_name=_("Employee"),
    )

    work_date = models.DateField(_("Work date"))

    hours = models.DecimalField(
        _("Hours"),
        max_digits=4,
        decimal_places=2,
        validators=[
            MinValueValidator(
                Decimal("0.01"),
                message=_("Hours must be greater " "than zero."),
            ),
            MaxValueValidator(
                Decimal("24.00"),
                message=_("Hours cannot exceed " "24 hours per day."),
            ),
        ],
    )

    invoice = models.ForeignKey(
        EmployeeSimpleInvoice,
        on_delete=models.SET_NULL,
        related_name="work_hours",
        verbose_name=_("Invoice"),
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        _("Created at"),
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        _("Updated at"),
        auto_now=True,
    )

    class Meta:
        verbose_name = _("Employee work hours")
        verbose_name_plural = _("Employee work hours")

        ordering = ["work_date"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "employee",
                    "work_date",
                ],
                name=("unique_employee_" "work_hours_date"),
            ),
            models.CheckConstraint(
                condition=(models.Q(hours__gt=0) & models.Q(hours__lte=24)),
                name=("employee_work_hours_" "valid_hours"),
            ),
        ]

    def clean(self) -> None:
        super().clean()

        errors = {}

        if self.work_date is not None and self.work_date > timezone.localdate():
            errors["work_date"] = _(
                "Work hours cannot be " "recorded for a future date."
            )

        if self.hours is not None:
            hours = Decimal(str(self.hours))

            if hours % WORK_HOURS_STEP != Decimal("0.00"):
                errors["hours"] = _("Hours must be entered " "in 0.10-hour increments.")

        if self.invoice_id:
            if self.employee_id is not None and (
                self.invoice.employee_id != self.employee_id
            ):
                errors["invoice"] = _(
                    "The invoice must belong " "to the same employee."
                )

            if self.work_date is not None and not (
                self.invoice.period_start <= self.work_date <= self.invoice.period_end
            ):
                errors["invoice"] = _(
                    "The work date must be " "within the invoice period."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.employee} | " f"{self.work_date} | " f"{self.hours}h"


class CheatSheet(models.Model):
    name = models.CharField(
        _("Name"),
        max_length=100,
        unique=True,
    )

    class Meta:
        verbose_name = _("Cheat sheet")
        verbose_name_plural = _("Cheat sheets")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CheatSheetStep(models.Model):
    cheatsheet = models.ForeignKey(
        CheatSheet,
        on_delete=models.CASCADE,
        related_name="steps",
        verbose_name=_("Cheat sheet"),
    )

    step_number = models.PositiveSmallIntegerField(
        _("Step number"),
        validators=[MinValueValidator(1)],
    )

    image = models.ImageField(
        _("Image"),
        upload_to=(cheatsheet_step_image_path),
    )

    description = models.TextField(
        _("Description"),
        blank=True,
    )

    class Meta:
        verbose_name = _("Cheat sheet step")
        verbose_name_plural = _("Cheat sheet steps")

        ordering = [
            "cheatsheet",
            "step_number",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "cheatsheet",
                    "step_number",
                ],
                name=("unique_step_number_" "per_cheatsheet"),
            )
        ]

    def __str__(self) -> str:
        return f"{self.cheatsheet.name} " f"- Step " f"{self.step_number}"
