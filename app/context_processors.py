from django.contrib.auth.models import Group

def user_role(request):
    user = getattr(request, 'user', None)
    if user and getattr(user, 'is_authenticated', False):
        groups = user.groups.values_list('name', flat=True)  # Get the names of groups
        group_name = groups[0] if groups else "No Role"  # Assuming one role per user
        return {
            'username': user.username,
            'user_role': group_name
        }
    return {}  # Empty context if user is not authenticated


from django.contrib.auth.models import Group

def admin_groups(request):
    # Get all groups
    groups = Group.objects.all()
    return {'all_groups': groups}


from .models import GroupButton

def group_buttons(request):
    return {
        'group_buttons': GroupButton.objects.all()
    }

from .models import ModuleVisibility 

def modules_with_submodules(request):
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
        return {}  # Return an empty context for unauthenticated users

    # Ensure ModuleVisibility exists for the logged-in user
    module_visibility, _ = ModuleVisibility.objects.get_or_create(user=user)
    enabled_modules = module_visibility.get_enabled_modules()

    # Prefetch SubmoduleVisibility for the user to avoid repeated queries
    submodule_visibility_map = {
        submodule.submodule_id: submodule.is_visible
        for submodule in user.submodule_visibility.all()
    }

    # Prepare modules and submodules based on visibility
    modules_with_submodules = {}

    for module in enabled_modules:
        visible_submodules = [
            submodule for submodule in module.submodules.all()
            if submodule.is_active and submodule_visibility_map.get(submodule.id, False)
        ]

        # Add the module to the dictionary regardless of submodule visibility
        modules_with_submodules[module] = visible_submodules

    return {
        'modules_with_submodules': modules_with_submodules,
    }


