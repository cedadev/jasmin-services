# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-21 15:59
from __future__ import unicode_literals

import django.core.validators
import jasmin_ldap_django.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("jasmin_services", "0004_migrate_ldap_group_data"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="ldapgroupbehaviour",
            name="group_dn",
        ),
    ]
