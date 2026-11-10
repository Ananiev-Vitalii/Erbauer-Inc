from django.db import migrations, models
from django.db.models.functions import Lower


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="employee",
            constraint=models.UniqueConstraint(
                Lower("email"), name="employee_email_lower_unique"
            ),
        ),
    ]
