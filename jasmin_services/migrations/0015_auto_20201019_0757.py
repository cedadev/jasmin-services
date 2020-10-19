# Generated by Django 2.2.4 on 2020-10-19 07:57

import django.core.validators
from django.db import migrations
import jasmin_ldap_django.models


class Migration(migrations.Migration):

    dependencies = [
        ('jasmin_services', '0014_new_grant_deletions'),
    ]

    operations = [
        migrations.CreateModel(
            name='CedaLdapGroup',
            fields=[
                ('name', jasmin_ldap_django.models.CharField(db_column='cn', error_messages={'max_length': 'Name must have at most %(limit_value)d characters.', 'unique': 'Name is already in use.'}, max_length=50, primary_key=True, serialize=False, validators=[django.core.validators.RegexValidator(message='Name must start with a letter.', regex='^[a-zA-Z]'), django.core.validators.RegexValidator(message='Name must end with a letter or number.', regex='[a-zA-Z0-9]$'), django.core.validators.RegexValidator(message='Name must contain letters, numbers, _ and -.', regex='^[a-zA-Z0-9_-]+$')])),
                ('description', jasmin_ldap_django.models.TextField(blank=True, db_column='description')),
                ('member_uids', jasmin_ldap_django.models.ListField(blank=True, db_column='memberUid')),
                ('gidNumber', jasmin_ldap_django.models.PositiveIntegerField(blank=True, unique=True)),
            ],
            options={
                'verbose_name': 'CEDA LDAP Group',
                'verbose_name_plural': None,
                'ordering': ['name'],
                'abstract': False,
                'managed': False,
            },
        ),
    ]
