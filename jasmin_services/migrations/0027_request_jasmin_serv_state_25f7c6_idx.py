# Generated by Django 5.1.5 on 2025-02-05 09:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jasmin_services", "0026_alter_request_internal_comment"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="request",
            index=models.Index(fields=["state"], name="jasmin_serv_state_25f7c6_idx"),
        ),
    ]
