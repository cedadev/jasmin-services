# Generated by Django 3.2.16 on 2022-12-20 09:11

from django.db import migrations
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        ('jasmin_services', '0022_rename_instution_countries'),
    ]

    operations = [
        migrations.AlterField(
            model_name='service',
            name='institution_countries',
            field=django_countries.fields.CountryField(blank=True, help_text="Coutries a user's institute must be located to begin approval. Hold ctrl or cmd for mac to select multiple countries. Leave blank for any country.", max_length=747, multiple=True),
        ),
    ]
