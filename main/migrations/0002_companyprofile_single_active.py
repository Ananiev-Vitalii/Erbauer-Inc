from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="companyprofile",
            constraint=models.UniqueConstraint(
                fields=["is_active"],
                condition=models.Q(is_active=True),
                name="main_single_active_company_profile",
                violation_error_message=(
                    "Only one company profile can be active. "
                    "Deactivate the current profile first."
                ),
            ),
        ),
    ]
