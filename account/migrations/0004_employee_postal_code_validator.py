import re

from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0003_employeesimpleinvoice_preparing_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="employee",
            name="postal_code",
            field=models.CharField(
                blank=True,
                max_length=7,
                validators=[
                    RegexValidator(
                        regex=r"\A[ABCEGHJ-NPRSTVXY][0-9][ABCEGHJ-NPRSTV-Z] ?"
                        r"[0-9][ABCEGHJ-NPRSTV-Z][0-9]\Z",
                        flags=re.IGNORECASE | re.ASCII,
                        message="Enter a valid Canadian postal code.",
                    ),
                ],
                verbose_name="Postal code",
            ),
        ),
    ]
