from django.db import migrations


def create_service_roles(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name='Service Engineer')
    Group.objects.get_or_create(name='Service Manager')


def remove_service_roles(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=['Service Engineer', 'Service Manager']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('apage', '0013_alter_siteamcwaterreport_options_and_more'),
    ]

    operations = [
        migrations.RunPython(create_service_roles, remove_service_roles),
    ]
