from django.db import models
from django.contrib.auth.models import User
class UserActivityLog(models.Model):
    ACTION_CHOICES = [
        ('added', 'User Added'),
        ('modified', 'User Modified'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    password = models.CharField(max_length=128)  # Store hashed password
    created_at = models.DateTimeField(auto_now_add=True)  # Date of creation
    updated_at = models.DateTimeField(auto_now=True)  # Date of modification

    def __str__(self):
        return f"{self.action} by {self.user} on {self.created_at}" 

class GroupButton(models.Model):
    name = models.CharField(max_length=100, unique=True)  # Group name
    url_name = models.CharField(max_length=100)  # URL name for the group

    def __str__(self):
        return self.name
    




# ------------------------------------------------------------------MODULE VISIBILITY ------------------------------------------------------------
from django.db import models
from django.contrib.auth.models import User, Permission


class CoreModule(models.Model):
    """
    Stores the list of available modules.
    """
    name = models.CharField(max_length=100, unique=True)  # Module name (e.g., "CRM")
    description = models.TextField(blank=True, null=True)  # Optional description
    is_active = models.BooleanField(default=True)  # Globally enable or disable this module
    slug = models.SlugField(unique=True, blank=True, null=True)  # Slug field for URL

    def save(self, *args, **kwargs):
        # Automatically create a slug based on the name if it's not set
        if not self.slug:
            self.slug = self.name.lower().replace(' ', '-')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class SubModule(models.Model):
    """
    Stores submodules linked to a CoreModule.
    """
    module = models.ForeignKey(CoreModule, related_name='submodules', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # Submodule name (e.g., "Leads")
    is_active = models.BooleanField(default=True)  # Enable/disable this submodule
    slug = models.SlugField(unique=True, blank=True, null=True)  # Slug field for URL

    def save(self, *args, **kwargs):
        # Automatically create a slug based on the name if it's not set
        if not self.slug:
            self.slug = f"{self.name.lower().replace(' ', '_')}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.module.name} - {self.name}"


class ModuleVisibility(models.Model):
    """
    Tracks which modules a user has access to.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='module_visibility')
    enabled_modules = models.ManyToManyField(CoreModule, blank=True)

    def get_enabled_submodules(self):
        return SubModule.objects.filter(
            module=self.module,
            is_active=True,
            submodulevisibility__user=self.user,
            submodulevisibility__is_visible=True
        )

    def has_module_access(self, module_name):
        """
        Check if a specific module is enabled for the user.
        """
        return self.enabled_modules.filter(name__iexact=module_name).exists()

    def get_enabled_modules(self):
        """
        Returns a list of all enabled CoreModule objects for the user.
        """
        return self.enabled_modules.all()

    def get_enabled_module_names(self):
        """
        Returns a list of names of all enabled modules for the user.
        """
        return self.enabled_modules.values_list('name', flat=True)

    def sync_permissions(self):
        """
        Sync universal CRUD permissions for the user.
        """
        permissions = [
            'can_view',
            'can_add',
            'can_change',
            'can_delete',
        ]
        # First, clear the user's current permissions
        self.user.user_permissions.clear()

        # Add universal permissions to the user
        for perm_codename in permissions:
            permission = Permission.objects.filter(codename=perm_codename).first()
            if permission:
                self.user.user_permissions.add(permission)

        self.user.save()

    class Meta:
        verbose_name = "Module Visibility"
        verbose_name_plural = "Module Visibility"

    def __str__(self):
        return f"Module Visibility for {self.user.username}"


class SubModuleVisibility(models.Model):
    """
    Tracks visibility of submodules for a user.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submodule_visibility')
    submodule = models.ForeignKey(SubModule, on_delete=models.CASCADE, related_name='visibility')
    is_visible = models.BooleanField(default=False)

    class Meta:
        verbose_name = "SubModule Visibility"
        verbose_name_plural = "SubModule Visibility"

    def __str__(self):
        return f"{self.user.username} - {self.submodule.name} - Visible: {self.is_visible}"




class Zone(models.Model):
    name = models.CharField(max_length=100)
    
    def __str__(self):
        return self.name

class Division(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name
    
from django.contrib.auth.models import User, Group

from datetime import date
class Target(models.Model):
    value = models.CharField(max_length=100)
    deadline = models.DateField(default=date.today)  # Default to today's date
    
    def __str__(self):
        return str(self.value)
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=10, unique=True, editable=False)
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, default=None)
    groups = models.ManyToManyField(Group, blank=True)
    email = models.EmailField(unique=True)  # Ensure unique email
    contact_number = models.CharField(max_length=15, default="0000000000")
    date_of_birth = models.DateField(default="2000-01-01")
    division = models.ForeignKey(Division, on_delete=models.SET_NULL, null=True, blank=True, default=None)
    target= models.ForeignKey(Target, on_delete=models.SET_NULL, null=True, blank=True)
    is_xpredict = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to="profile_pics/", default="profile_pics/default.jpg")


    
    def save(self, *args, **kwargs):
        # Generate the employee ID for existing data if missing
        if not self.employee_id:
            # Start with the base 'XAS001' and check if it exists
            base_id = "XAS"
            base_number = 1
            
            # Try generating employee IDs and check if they already exist
            while True:
                # Format the employee ID with 3-digit numbers
                generated_id = f"{base_id}{base_number:03d}"

                # Check if this generated ID already exists in the database
                if not UserProfile.objects.filter(employee_id=generated_id).exists():
                    self.employee_id = generated_id
                    break
                base_number += 1
        # Sync email with User model
        if self.email and self.user.email != self.email:
            self.user.email = self.email
            self.user.save()
        
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.user.username}'s Profile"






