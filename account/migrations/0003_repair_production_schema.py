from django.db import migrations


def repair_production_schema(apps, schema_editor):
    connection = schema_editor.connection

    invoice_model = apps.get_model(
        "account",
        "EmployeeSimpleInvoice",
    )
    work_hours_model = apps.get_model(
        "account",
        "EmployeeWorkHours",
    )

    invoice_table = invoice_model._meta.db_table
    work_hours_table = work_hours_model._meta.db_table

    with connection.cursor() as cursor:
        table_names = set(
            connection.introspection.table_names(cursor)
        )

    if invoice_table not in table_names:
        raise RuntimeError(
            f"Expected table {invoice_table!r} does not exist."
        )

    with connection.cursor() as cursor:
        invoice_columns = {
            column.name
            for column in connection.introspection.get_table_description(
                cursor,
                invoice_table,
            )
        }

    for field_name in (
        "invoice_month",
        "invoice_year",
    ):
        field = invoice_model._meta.get_field(field_name)

        if field.column not in invoice_columns:
            schema_editor.add_field(
                invoice_model,
                field,
            )
            invoice_columns.add(field.column)

    with connection.cursor() as cursor:
        table_names = set(
            connection.introspection.table_names(cursor)
        )

    if work_hours_table not in table_names:
        schema_editor.create_model(work_hours_model)


class Migration(migrations.Migration):

    dependencies = [
        (
            "account",
            "0002_employeesimpleinvoice_created_at_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            repair_production_schema,
            reverse_code=migrations.RunPython.noop,
        ),
    ]