# Generated by Django 2.2.4 on 2020-08-13 07:52

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import jasmin_ldap_django.models
import jasmin_services.models.access_control


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('jasmin_metadata', '0003_auto_20200730_1139'),
        ('auth', '0011_update_proxy_permissions'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
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
        migrations.CreateModel(
            name='Behaviour',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('polymorphic_ctype', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='polymorphic_jasmin_services.behaviour_set+', to='contenttypes.ContentType')),
            ],
            options={
                'abstract': False,
                'base_manager_name': 'objects',
            },
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.SlugField(help_text='Short name for the category, used in URLs', unique=True)),
                ('long_name', models.CharField(help_text='Long name for the category, used for display', max_length=250)),
                ('position', models.PositiveIntegerField(default=9999, help_text='Number defining where the category appears in listings. Categories are ordered in ascending order by this field, then alphabetically by name within that.')),
            ],
            options={
                'verbose_name_plural': 'Categories',
                'ordering': ('position', 'long_name'),
            },
        ),
        migrations.CreateModel(
            name='Grant',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('granted_by', models.CharField(max_length=200)),
                ('granted_at', models.DateTimeField(auto_now_add=True)),
                ('expires', models.DateField(default=jasmin_services.models.access_control._default_expiry, verbose_name='expiry date')),
                ('revoked', models.BooleanField(default=False)),
                ('user_reason', models.TextField(blank=True, help_text='<a href="http://daringfireball.net/projects/markdown/syntax" target="_blank">Markdown syntax</a> allowed, but no raw HTML. Examples: **bold**, *italic*, indent 4 spaces for a code block.', verbose_name='Reason for revocation (user)')),
                ('internal_reason', models.TextField(blank=True, help_text='<a href="http://daringfireball.net/projects/markdown/syntax" target="_blank">Markdown syntax</a> allowed, but no raw HTML. Examples: **bold**, *italic*, indent 4 spaces for a code block.', verbose_name='Reason for revocation (internal)')),
            ],
            options={
                'ordering': ('role__service__category__position', 'role__service__category__long_name', 'role__service__position', 'role__service__name', 'role__position', 'role__name', '-granted_at'),
                'get_latest_by': 'granted_at',
            },
        ),
        migrations.CreateModel(
            name='LdapGroupBehaviour',
            fields=[
                ('behaviour_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='jasmin_services.Behaviour')),
                ('ldap_model', models.CharField(help_text='The LDAP group model to use.', max_length=100, verbose_name='LDAP model')),
                ('group_name', models.CharField(help_text='The name of the LDAP group to use.', max_length=100, verbose_name='LDAP group name')),
            ],
            options={
                'verbose_name': 'LDAP Group Behaviour',
            },
            bases=('jasmin_services.behaviour',),
        ),
        migrations.CreateModel(
            name='LdapTagBehaviour',
            fields=[
                ('behaviour_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='jasmin_services.Behaviour')),
                ('tag', models.CharField(max_length=100, unique=True, validators=[django.core.validators.RegexValidator(regex='^[a-zA-Z0-9_:-]+$')], verbose_name='LDAP Tag')),
            ],
            options={
                'verbose_name': 'LDAP Tag Behaviour',
            },
            bases=('jasmin_services.behaviour',),
        ),
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.SlugField(help_text='The name of the service. This is also used in URLs.')),
                ('summary', models.TextField(help_text='One-line description of the service, shown in listings. No special formatting allowed.')),
                ('description', models.TextField(blank=True, default='', help_text='Full description of the service, shown on the details page. Markdown formatting is allowed.', null=True)),
                ('hidden', models.BooleanField(default=True, help_text='Prevents the service appearing in listings unless the user has an active grant or request for it. The service details page will still be accessible to anybody who knows the URL.')),
                ('position', models.PositiveIntegerField(default=9999, help_text='Number defining where the service appears in listings. Services are ordered in ascending order by category, then by this field, then alphabetically by name.')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='services', related_query_name='service', to='jasmin_services.Category')),
            ],
            options={
                'ordering': ('category__position', 'category__long_name', 'position', 'name'),
                'unique_together': {('category', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Role',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, verbose_name='role name')),
                ('description', models.CharField(blank=True, max_length=250)),
                ('hidden', models.BooleanField(default=True, help_text='Prevents the role appearing in listings unless the user has an active grant or request for it.')),
                ('position', models.PositiveIntegerField(default=9999, help_text='Number defining where the role appears in listings. Roles are ordered first by their service, then in ascending order by this field, then alphabetically.')),
                ('behaviours', models.ManyToManyField(related_name='roles', related_query_name='role', to='jasmin_services.Behaviour')),
                ('metadata_form', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='jasmin_metadata.Form')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='roles', related_query_name='role', to='jasmin_services.Service')),
            ],
            options={
                'ordering': ('service__category__position', 'service__category__long_name', 'service__position', 'service__name', 'position', 'name'),
                'permissions': (('view_users_role', 'Can view users with role'), ('send_message_role', 'Can send messages to users with role')),
                'unique_together': {('service', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Request',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('requested_by', models.CharField(max_length=200)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('state', models.CharField(choices=[('APPROVED', 'APPROVED'), ('PENDING', 'PENDING'), ('REJECTED', 'REJECTED')], default='PENDING', max_length=8)),
                ('user_reason', models.TextField(blank=True, help_text='<a href="http://daringfireball.net/projects/markdown/syntax" target="_blank">Markdown syntax</a> allowed, but no raw HTML. Examples: **bold**, *italic*, indent 4 spaces for a code block.', verbose_name='Reason for rejection (user)')),
                ('internal_reason', models.TextField(blank=True, help_text='<a href="http://daringfireball.net/projects/markdown/syntax" target="_blank">Markdown syntax</a> allowed, but no raw HTML. Examples: **bold**, *italic*, indent 4 spaces for a code block.', verbose_name='Reason for rejection (internal)')),
                ('grant', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='request', to='jasmin_services.Grant')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requests', related_query_name='request', to='jasmin_services.Role')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ('role__service__category__position', 'role__service__category__long_name', 'role__service__position', 'role__service__name', 'role__position', 'role__name', '-requested_at'),
                'permissions': (('decide_request', 'Can make decisions on requests'),),
                'get_latest_by': 'requested_at',
            },
        ),
        migrations.AddField(
            model_name='grant',
            name='role',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grants', related_query_name='grant', to='jasmin_services.Role'),
        ),
        migrations.AddField(
            model_name='grant',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name='RoleObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_pk', models.CharField(help_text='Primary key of the object to which the permission applies.', max_length=150, verbose_name='Object primary key')),
                ('content_type', models.ForeignKey(help_text='Content type of the object to which the permission applies.', on_delete=django.db.models.deletion.CASCADE, to='contenttypes.ContentType', verbose_name='Object content type')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='object_permissions', related_query_name='object_permission', to='jasmin_services.Role')),
            ],
            options={
                'unique_together': {('role', 'permission', 'content_type', 'object_pk')},
            },
        ),
        migrations.CreateModel(
            name='JoinJISCMailListBehaviour',
            fields=[
                ('behaviour_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='jasmin_services.Behaviour')),
                ('list_name', models.CharField(help_text='The name of the JISCMail mailing list to join', max_length=100, unique=True)),
                ('joined_users', models.ManyToManyField(blank=True, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Join JISCMail List Behaviour',
            },
            bases=('jasmin_services.behaviour',),
        ),
    ]
