# Generated by Django 2.2.9 on 2021-11-08 13:31

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import jasmin_services.models


class Migration(migrations.Migration):
    dependencies = [
        ("jasmin_services", "0012_auto_20211108_1330"),
    ]

    operations = [
        migrations.CreateModel(
            name="Access",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="accesses",
                        related_query_name="access",
                        to="jasmin_services.Role",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": (
                    "role__service__category__position",
                    "role__service__category__long_name",
                    "role__service__position",
                    "role__service__name",
                    "role__position",
                    "role__name",
                ),
                "verbose_name_plural": "accesses",
                "unique_together": {("role", "user")},
            },
        ),
        migrations.CreateModel(
            name="Grant_new",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "access",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="grants",
                        related_query_name="grant",
                        to="jasmin_services.Access",
                    ),
                ),
                ("granted_by", models.CharField(max_length=200)),
                ("granted_at", models.DateTimeField()),
                (
                    "expires",
                    models.DateField(
                        default=jasmin_services.models.grant._default_expiry,
                        verbose_name="expiry date",
                    ),
                ),
                ("revoked", models.BooleanField(default=False)),
                (
                    "user_reason",
                    models.TextField(
                        blank=True,
                        help_text='<a href="http://daringfireball.net/projects/markdown/syntax" target="_blank">Markdown syntax</a> allowed, but no raw HTML. Examples: **bold**, *italic*, indent 4 spaces for a code block.',
                        verbose_name="Reason for revocation (user)",
                    ),
                ),
                (
                    "internal_reason",
                    models.TextField(
                        blank=True,
                        help_text='<a href="http://daringfireball.net/projects/markdown/syntax" target="_blank">Markdown syntax</a> allowed, but no raw HTML. Examples: **bold**, *italic*, indent 4 spaces for a code block.',
                        verbose_name="Reason for revocation (internal)",
                    ),
                ),
                (
                    "previous_grant",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.SET_NULL,
                        related_name="next_grant",
                        to="jasmin_services.Grant_new",
                    ),
                ),
            ],
            options={
                "ordering": (
                    "access__role__service__category__position",
                    "access__role__service__category__long_name",
                    "access__role__service__position",
                    "access__role__service__name",
                    "access__role__position",
                    "access__role__name",
                    "-granted_at",
                ),
                "get_latest_by": "granted_at",
            },
        ),
        migrations.AddField(
            model_name="request",
            name="previous_request",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="next_request",
                to="jasmin_services.Request",
            ),
        ),
        migrations.AddField(
            model_name="request",
            name="resulting_grant",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="request",
                to="jasmin_services.Grant_new",
            ),
        ),
        migrations.AddField(
            model_name="request",
            name="previous_grant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="next_requests",
                to="jasmin_services.Grant_new",
            ),
        ),
        migrations.AddField(
            model_name="request",
            name="access",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="requests",
                related_query_name="request",
                to="jasmin_services.Access",
            ),
        ),
    ]
