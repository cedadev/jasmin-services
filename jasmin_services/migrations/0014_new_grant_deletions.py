# Generated by Django 2.2.4 on 2020-10-16 12:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jasmin_services', '0013_new_grant_migrate_data'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='request',
            options={'get_latest_by': 'requested_at', 'ordering': ('access__role__service__category__position', 'access__role__service__category__long_name', 'access__role__service__position', 'access__role__service__name', 'access__role__position', 'access__role__name', '-requested_at'), 'permissions': (('decide_request', 'Can make decisions on requests'),)},
        ),
        migrations.RemoveField(
            model_name='request',
            name='role',
        ),
		migrations.RemoveField(
            model_name='request',
            name='user',
        ),
        migrations.RemoveField(
            model_name='request',
            name='grant',
        ),
        migrations.DeleteModel(
            name='Grant',
        ),
		migrations.RenameModel('Grant_new','Grant'),
    ]