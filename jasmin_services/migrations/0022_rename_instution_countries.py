# Generated by Django 3.2.16 on 2022-12-20 09:08

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("jasmin_services", "0021_auto_20220914_0852"),
    ]

    operations = [
        migrations.RenameField("service", "instution_countries", "institution_countries"),
    ]
