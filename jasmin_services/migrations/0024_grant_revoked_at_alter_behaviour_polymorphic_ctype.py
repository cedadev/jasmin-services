# Generated by Django 4.1.9 on 2023-05-31 09:57

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("jasmin_services", "0023_alter_service_institution_countries"),
    ]

    operations = [
        migrations.AddField(
            model_name="grant",
            name="revoked_at",
            field=models.DateTimeField(
                blank=True,
                default=None,
                help_text="Date on which this grant was revoked.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="behaviour",
            name="polymorphic_ctype",
            field=models.ForeignKey(
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="polymorphic_%(app_label)s.%(class)s_set+",
                to="contenttypes.contenttype",
            ),
        ),
    ]
