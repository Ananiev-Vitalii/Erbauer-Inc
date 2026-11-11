from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0002_employee_email_lower_unique"),
    ]

    operations = [
        migrations.AlterField(
            model_name="employeesimpleinvoice",
            name="status",
            field=models.CharField(
                choices=[
                    ("processing", "Processing"),
                    ("preparing", "Preparing"),
                    ("sent", "Sent"),
                    ("failed", "Failed"),
                ],
                default="processing",
                max_length=20,
                verbose_name="Status",
            ),
        ),
    ]
