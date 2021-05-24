# Generated by Django 2.2.9 on 2021-03-17 08:04

import django.core.validators
from django.db import migrations, models
import jasmin_ldap_django.models


class Migration(migrations.Migration):

    dependencies = [
        ('jasmin_services', '0010_auto_20190916_1328'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='ceda_managed',
            field=models.BooleanField(default=False, help_text='Whether the service is managed by CEDA.'),
        ),
    ]
