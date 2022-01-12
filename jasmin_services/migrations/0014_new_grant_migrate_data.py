# Generated by Django 2.2.9 on 2021-11-08 13:32

from django.db import migrations


def get_or_create_access(Access,
                         user,
                         role):
                
    return Access.objects.get_or_create(user = user, role = role)


def create_grant_new(Grant_new,
                     access,
                     old_grant):
                
    return Grant_new.objects.create(
        access = access,
        granted_by = old_grant.granted_by,
        granted_at = old_grant.granted_at,
        expires = old_grant.expires,
        revoked = old_grant.revoked,
        user_reason = old_grant.user_reason,
        internal_reason = old_grant.internal_reason,
        previous_grant = None
    )
    

def migrate(apps, schema_editor):
    """
    Migration that creates an Access and Grant_new, and copies data from the 
    current grant.
    """
    Access = apps.get_model("jasmin_services", "Access")	
    Grant_new = apps.get_model("jasmin_services", "Grant_new")
    Request = apps.get_model("jasmin_services", "Request")
    
    for request in Request.objects.all():
        access, _ = get_or_create_access(Access, request.user, request.role)
        request.access = access
        if request.grant is not None:
            new_grant = create_grant_new(Grant_new, access, request.grant)
            request.resulting_grant = new_grant
        request.access = access
        request.save()
        
    for access in Access.objects.all():
        previous_grant = None
        for grant_new in Grant_new.objects.filter(access=access).order_by('granted_at'):
            if previous_grant:
                grant_new.previous_grant = previous_grant
                grant_new.save()
            previous_grant = grant_new


class Migration(migrations.Migration):

    dependencies = [
        ('jasmin_services', '0013_new_grant_additions'),
    ]

    operations = [
        migrations.RunPython(migrate),
    ]
