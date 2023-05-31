# Generated by Django 2.0.6 on 2018-06-11 15:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jasmin_services", "0007_flexible_roles_migrate_data"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="servicerolebehaviour",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="servicerolebehaviour",
            name="behaviour",
        ),
        migrations.RemoveField(
            model_name="servicerolebehaviour",
            name="service",
        ),
        migrations.AlterUniqueTogether(
            name="servicerolemetadataform",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="servicerolemetadataform",
            name="form",
        ),
        migrations.RemoveField(
            model_name="servicerolemetadataform",
            name="service",
        ),
        migrations.RemoveField(
            model_name="grant",
            name="role_old",
        ),
        migrations.RemoveField(
            model_name="grant",
            name="service",
        ),
        migrations.RemoveField(
            model_name="request",
            name="role_old",
        ),
        migrations.RemoveField(
            model_name="request",
            name="service",
        ),
        migrations.AlterField(
            model_name="grant",
            name="role_new",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="grants",
                related_query_name="grant",
                to="jasmin_services.Role",
            ),
        ),
        migrations.AlterField(
            model_name="request",
            name="role_new",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="requests",
                related_query_name="request",
                to="jasmin_services.Role",
            ),
        ),
        migrations.DeleteModel(
            name="ServiceRoleBehaviour",
        ),
        migrations.DeleteModel(
            name="ServiceRoleMetadataForm",
        ),
        migrations.RenameField(
            model_name="grant",
            old_name="role_new",
            new_name="role",
        ),
        migrations.RenameField(
            model_name="request",
            old_name="role_new",
            new_name="role",
        ),
    ]
