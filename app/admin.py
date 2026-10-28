from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin
from django.urls import path
from django.utils.html import format_html
from django.urls import reverse
from .models import UserActivityLog ,GroupButton , Division
from .views import manage_user_groups
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404, render, redirect



# Unregister the default User model admin to use the custom one
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass  # User is not registered yet, so we ignore the error


from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

def get_custom_crud_permissions(*args, **kwargs):
    """
    Fetch custom CRUD permissions associated with the universal content type.
    """
    # Fetch the generic ContentType created for universal permissions
    try:
        content_type = ContentType.objects.get(app_label='app', model='coremodule')
    except ContentType.DoesNotExist:
        # If ContentType doesn't exist for this, handle the error appropriately
        print("ContentType for 'global.universal' does not exist.")
        return Permission.objects.none()

    # Fetch permissions based on the content type and the CRUD permission codenames
    return Permission.objects.filter(
        content_type=content_type,
        codename__in=['add_profile', 'change_profile', 'delete_profile', 'view_profile']
    )



# Register custom view paths for managing permissions for Client, Employee, and Manager groups


# Register the UserActivityLog model
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'created_at', 'updated_at')


admin.site.register(UserActivityLog, UserActivityLogAdmin)


# Custom UserAdmin class
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.auth.admin import UserAdmin

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'is_staff', 'is_active', 'get_user_groups', 'manage_groups_button',)
    list_filter = ('groups', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username',)

    # Display the user's groups in list display
    def get_user_groups(self, user):
        return ", ".join([group.name for group in user.groups.all()])
    get_user_groups.short_description = 'Groups'

    # Button to redirect to user group management view
    def manage_groups_button(self, obj):
        return format_html('<a class="button" href="{}">Manage Groups</a>', reverse('admin:manage_user_groups'))
    manage_groups_button.short_description = 'Manage Groups'




# Register the User model with the custom UserAdmin
admin.site.register(User, CustomUserAdmin)


def manage_group_permissions(request, group_name):
    group = get_object_or_404(Group, name=group_name)
    permissions = get_custom_crud_permissions()  # Ensure this function returns all required permissions

    print("Permissions fetched:", permissions)  # Debugging line
    
    if request.method == 'POST':
        selected_permissions = request.POST.getlist('permissions')
        group.permissions.clear()
        for permission_id in selected_permissions:
            permission = Permission.objects.get(id=permission_id)
            group.permissions.add(permission)
        return redirect('admin:index')

    return render(request, 'admin/manage_group_permissions.html', {
        'group': group,
        'permissions': permissions
    })




from django.contrib import admin
from .models import GroupButton

# Optionally, you can create a custom admin class to control how the model appears in the admin interface
class GroupButtonAdmin(admin.ModelAdmin):
    list_display = ('name', 'url_name')  # Display these fields in the admin list view
    search_fields = ('name', 'url_name')  # Add a search bar for the fields
    ordering = ('name',)  # Order the list by 'name' field

# Register the model and the custom admin class
admin.site.register(GroupButton, GroupButtonAdmin)



# ------------------------------------------------------------------MODULE VISIBILITY ------------------------------------------------------------
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import ModuleVisibility ,CoreModule
from django.contrib import admin
from .models import ModuleVisibility, CoreModule ,SubModule ,SubModuleVisibility
from .forms import ModuleVisibilityForm

@admin.register(ModuleVisibility)
class ModuleVisibilityAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_enabled_modules_list')
    form = ModuleVisibilityForm

    def get_enabled_modules_list(self, obj):
        """
        Display the enabled modules as a comma-separated string in the admin list view.
        """
        return ", ".join([module.name for module in obj.enabled_modules.all()])

    get_enabled_modules_list.short_description = "Enabled Modules"

@admin.register(CoreModule)
class CoreModuleAdmin(admin.ModelAdmin):
    """
    Admin configuration for CoreModule.
    """
    list_display = ('name', 'description', 'is_active', 'slug')  # Include 'slug' in display
    prepopulated_fields = {'slug': ('name',)}  # Automatically populate 'slug' from 'name'
    search_fields = ('name', 'description')  # Required for dynamic linking in SubModuleAdmin
    list_filter = ('is_active',)


@admin.register(SubModule)
class SubModuleAdmin(admin.ModelAdmin):
    """
    Admin configuration for SubModule.
    """
    list_display = ('name', 'module', 'is_active','slug')
    search_fields = ('name', 'module__name')  # Allow searching for submodules
    list_filter = ('is_active', 'module')
    autocomplete_fields = ['module']  # Enable dynamic selection of CoreModule

@admin.register(SubModuleVisibility)
class SubModuleVisibilityAdmin(admin.ModelAdmin):
    list_display = ('user', 'submodule', 'is_visible')


from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile, Zone

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'user profile'
    fk_name = 'user'

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = UserAdmin.list_display + ('service_report_edit_allowed', 'manage_modules_button', 'manage_submodule_visibility_button')

    def service_report_edit_allowed(self, obj):
        profile = getattr(obj, 'userprofile', None)
        if obj.groups.filter(name='Service Report - View Only').exists():
            return False
        return profile.can_edit_service_reports if profile else True
    service_report_edit_allowed.boolean = True
    service_report_edit_allowed.short_description = 'SR Edit'


    def zone(self, obj):
        return obj.userprofile.zone if hasattr(obj, 'userprofile') else None
    
    def get_groups(self, obj):
        return ", ".join([group.name for group in obj.groups.all()])
    get_groups.short_description = 'Groups'  # Set header for groups column
    def manage_modules_button(self, obj):
        return format_html(
            '<a class="button" href="{}">Manage Modules</a>',
            reverse('manage_module_visibility', args=[obj.id])
        )
    manage_modules_button.short_description = 'Manage Modules'

    def response_add(self, request, obj, post_url_continue=None):
        # Redirect to manage_module_visibility after user creation
        return redirect(reverse('manage_module_visibility', kwargs={'user_id': obj.id}))
        # Button to redirect to submodule visibility management view
    def manage_submodule_visibility_button(self, obj):
        url = reverse('manage_submodule_visibility', args=[obj.id])
        return format_html('<a class="button" href="{}">Manage Submodule Visibility</a>', url)
    manage_submodule_visibility_button.short_description = 'Manage Submodule Visibility'
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('group/<str:group_name>/permissions/', manage_group_permissions, name='manage_group_permissions'),
            path('manage_user_groups/', manage_user_groups, name='manage_user_groups'),
        ]
        return custom_urls + urls
    
def save_model(self, request, obj, form, change):
    """Override save method to trigger user profile save when a new user is created"""
    super().save_model(request, obj, form, change)

    # Ensure UserProfile is created only if it doesn't exist
    if not change:  # Only for new users
        try:
            # Check if the profile already exists and create only if it doesn't
            user_profile, created = UserProfile.objects.get_or_create(user=obj)
            if created:
                print(f"UserProfile created for {obj.username}")
        except Exception as e:
            # Handle any errors that might occur, like database issues
            print(f"Error creating UserProfile for {obj.username}: {e}")


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.register(Zone)
admin.site.register(Division)




