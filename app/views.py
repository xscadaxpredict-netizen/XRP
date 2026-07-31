from django.shortcuts import render, redirect
from .models import SubModule
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from app.models import ModuleVisibility
from django.db.models import Prefetch
from django.contrib.auth.views import LoginView

class CustomLoginView(LoginView):
    def form_valid(self, form):
        remember_me = self.request.POST.get('remember_me')
        if remember_me:
            # Set session to expire in 2 weeks
            self.request.session.set_expiry(1209600)
        else:
            # Set session to expire when browser closes
            self.request.session.set_expiry(0)
        return super().form_valid(form)

def HOME(request):
    return render(request ,'apage/HOME.html')

@permission_required('auth.change_group')
def manage_user_groups(request):
    users = User.objects.all()
    all_groups = Group.objects.all()

    if request.method == 'POST':
        for user in users:
            selected_group_ids = request.POST.getlist(f'user_{user.id}')
            user.groups.clear()  # Clear existing groups
            user.groups.add(*selected_group_ids)  # Add selected groups

        return redirect('admin:auth_user_changelist')

    return render(request, 'admin/manage_user_groups.html', {
        'users': users,
        'all_groups': all_groups,
})

# ------------------------------------------------------------------MODULE VISIBILITY ------------------------------------------------------------
from django.shortcuts import render, get_object_or_404, redirect
from .models import User, ModuleVisibility, CoreModule
from .forms import ModuleVisibilityForm
from django.contrib.auth.decorators import login_required, permission_required

@login_required
@permission_required('auth.change_user')
def manage_module_visibility(request, user_id):
    user = get_object_or_404(User, id=user_id)
    module_visibility, created = ModuleVisibility.objects.get_or_create(user=user)

    if request.method == 'POST':
        form = ModuleVisibilityForm(request.POST, instance=module_visibility)
        if form.is_valid():
            form.save()
            module_visibility.sync_permissions()
            return redirect('master_list', app_label='auth', model_name='user')
    else:
        form = ModuleVisibilityForm(instance=module_visibility)

    return render(request, 'admin/manage_module_visibility.html', {
        'form': form,
        'user': user,
    })
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

def get_module_permissions(user):
    """
    Fetch universal CRUD permissions for the user.
    """
    return {
        'add_profile': user.has_perm('app.add_profile'),
        'change_profile': user.has_perm('app.change_profile'),
        'delete_profile': user.has_perm('app.delete_profile'),
        'view_profile': user.has_perm('app.view_profile'),
    }


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

from django.contrib.auth.decorators import permission_required
@login_required
def module_dashboard(request, module_slug):

        # --------------------------***********-----------------------------

    module_visibility, created = ModuleVisibility.objects.get_or_create(user=request.user)
    enabled_modules = module_visibility.get_enabled_modules()

    # Prefetch SubmoduleVisibility for the user to avoid repeated queries
    submodule_visibility_map = {
        submodule.submodule_id: submodule.is_visible
        for submodule in request.user.submodule_visibility.all()
    }

    # Prepare modules and submodules based on visibility
    modules_with_submodules = {}

    for module in enabled_modules:
        visible_submodules = [
            submodule for submodule in module.submodules.all()
            if submodule.is_active and submodule_visibility_map.get(submodule.id, False)
        ]
        if visible_submodules:
            modules_with_submodules[module] = visible_submodules
        # --------------------------***********-----------------------------


    module = get_object_or_404(CoreModule, slug=module_slug, is_active=True)
    permissions = get_module_permissions(request.user)  # Get universal CRUD permissions
    if module_slug == 'profile-management':  # Special case for Profile management
        if permissions.get('view_profile'):
            profiles = Profile.objects.all()  # You can filter the profiles as needed
        else:
            profiles = Profile.objects.none()  # No profiles if no permission
        context = {**permissions, 'module': module_slug,
                    'modules_with_submodules': modules_with_submodules,
                    'profiles': profiles}
        return render(request, 'app/home.html', context )

    # Fallback to a generic dashboard for other modules
    templates = [
        f"app/{module.slug}.html",
        "app/module_dashboard.html",
    ]


    print(permissions)  # Debugging to verify permissions
    return render(request, templates, {
        'module': module,
        'modules_with_submodules': modules_with_submodules,
        **permissions,  # Pass permissions to the context
    })


from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from .models import User, ModuleVisibility, CoreModule, SubModuleVisibility
from django.shortcuts import redirect

@login_required
def manage_submodule_visibility(request, user_id):
    # Fetch the user for whom submodule visibility is being managed
    user = get_object_or_404(User, id=user_id)

    # Get enabled module IDs for the user
    enabled_module_ids = ModuleVisibility.objects.filter(user=user).values_list('enabled_modules', flat=True)
    # Fetch modules with their submodules
    modules = CoreModule.objects.filter(id__in=enabled_module_ids).prefetch_related('submodules')

    # Prefetch SubmoduleVisibility for the user
    submodule_visibility_map = {
        subvisibility.submodule_id: subvisibility.is_visible
        for subvisibility in SubModuleVisibility.objects.filter(user=user)
    }

    # Handle form submission to update visibility
    if request.method == 'POST':
        for module in modules:
            for submodule in module.submodules.all():
                # Determine checkbox status
                is_visible = f"submodule_{submodule.id}" in request.POST

                # Clean up duplicates if they exist to prevent MultipleObjectsReturned
                sub_vis_qs = SubModuleVisibility.objects.filter(user=user, submodule=submodule)
                if sub_vis_qs.count() > 1:
                    first_id = sub_vis_qs.first().id
                    sub_vis_qs.exclude(id=first_id).delete()

                # Update or create the SubModuleVisibility entry
                SubModuleVisibility.objects.update_or_create(
                    user=user,
                    submodule=submodule,
                    defaults={'is_visible': is_visible},
                )

        # Redirect after saving
        return redirect('master_list', app_label='auth', model_name='user')

    # Prepare a dictionary of modules with their submodules and visibility status
    user_visibility_data = {
        module: [
            {
                'submodule': submodule,
                'is_visible': submodule_visibility_map.get(submodule.id, False),
            }
            for submodule in module.submodules.all() if submodule.is_active
        ]
        for module in modules
    }

    # Render the template with the prepared context
    return render(request, 'admin/manage_submodule_visibility.html', {
        'user': user,
        'user_visibility_data': user_visibility_data,
    })    


# views.py

from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse

@login_required
def submodule_visibility(request, submodule_slug):
    # Fetch user permissions and visible modules/submodules as before
    permissions = get_module_permissions(request.user)
    module_visibility, created = ModuleVisibility.objects.get_or_create(user=request.user)
    enabled_modules = module_visibility.get_enabled_modules()

    submodule_visibility_map = {
        submodule.submodule_id: submodule.is_visible
        for submodule in request.user.submodule_visibility.all()
    }

    modules_with_submodules = {}
    for module in enabled_modules:
        visible_submodules = [
            submodule for submodule in module.submodules.all()
            if submodule.is_active and submodule_visibility_map.get(submodule.id, False)
        ]
        if visible_submodules:
            modules_with_submodules[module] = visible_submodules

    # Fetch the submodule using the slug
    # submodule = get_object_or_404(SubModule, slug=submodule_slug, is_active=True)

    # # Map slugs to view names
    # slug_to_view_map = {
    #     'generalreport': 'generalreport',
    #     'servicereport': 'servicereport',
    #     'maintenance_checklist': 'maintenance_checklist',
    #     'mom': 'mom',
    # }

    # # Check if the slug exists in the map and redirect
    # if submodule.slug in slug_to_view_map:
    #     return redirect(slug_to_view_map[submodule.slug]) 
        
    #      # Redirects to the matching view

    return redirect(reverse(submodule_slug))

    # If no mapping is found, you can handle the case (e.g., show 404 or an error page)
    return render(request, 'app/module_dashboard.html')




