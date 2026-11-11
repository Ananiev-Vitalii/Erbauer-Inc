import re

from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _

canadian_postal_code_validator = RegexValidator(
    regex=r"\A[ABCEGHJ-NPRSTVXY][0-9][ABCEGHJ-NPRSTV-Z] ?"
    r"[0-9][ABCEGHJ-NPRSTV-Z][0-9]\Z",
    flags=re.IGNORECASE | re.ASCII,
    message=_("Enter a valid Canadian postal code."),
)


def normalize_canadian_postal_code(value: str) -> str:
    """Format valid codes without repairing invalid input before validation."""
    normalized = value.strip()
    if canadian_postal_code_validator.regex.fullmatch(normalized):
        normalized = normalized.upper()
        return f"{normalized[:3]} {normalized[-3:]}"
    return normalized
