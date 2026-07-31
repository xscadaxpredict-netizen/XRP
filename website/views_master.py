from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.apps import apps
from django.contrib import messages
from django.forms import modelform_factory
from django.contrib.auth.models import User
from django import forms
from app.models import UserProfile, Zone, Division

MASTER_MODELS = [
    {'app_label': 'auth', 'model_name': 'user', 'name': 'Users', 'icon': 'bi-people', 'description': 'Manage system users and access'},
    {'app_label': 'apage', 'model_name': 'site', 'name': 'Sites', 'icon': 'bi-building', 'description': 'Manage site locations and details'},
    {'app_label': 'website', 'model_name': 'conveyancesite', 'name': 'Conveyance Sites', 'icon': 'bi-geo-alt-fill', 'description': 'Manage conveyance sites and distances'},
    {'app_label': 'website', 'model_name': 'conveyance', 'name': 'Conveyances', 'icon': 'bi-truck', 'description': 'Manage conveyance vehicle rates'},
    {'app_label': 'app', 'model_name': 'zone', 'name': 'Zones', 'icon': 'bi-geo-alt', 'description': 'Manage regional zones'},
    {'app_label': 'app', 'model_name': 'division', 'name': 'Divisions', 'icon': 'bi-diagram-2', 'description': 'Manage company divisions'},
    {'app_label': 'indent', 'model_name': 'department', 'name': 'Departments', 'icon': 'bi-briefcase', 'description': 'Manage organizational departments'},
    {'app_label': 'Riva', 'model_name': 'products', 'name': 'Products', 'icon': 'bi-box-seam', 'description': 'Manage product catalog'},
    {'app_label': 'Riva', 'model_name': 'executive', 'name': 'Executives', 'icon': 'bi-person-badge', 'description': 'Manage sales executives'},
]

def get_master_model_info(app_label, model_name):
    for m in MASTER_MODELS:
        if m['app_label'] == app_label and m['model_name'] == model_name:
            return m
    return None

class MasterModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field, forms.ModelMultipleChoiceField):
                field.widget = forms.CheckboxSelectMultiple()
                field.widget.attrs['class'] = 'form-check-input mb-2'

class UserMasterForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control rounded-3 shadow-sm'}),
        required=False,
        help_text="Leave blank to keep current password when updating."
    )
    zone = forms.ModelChoiceField(
        queryset=Zone.objects.all(),
        required=False,
        label="Zone",
        widget=forms.Select(attrs={'class': 'form-select rounded-3 shadow-sm'})
    )
    division = forms.ModelChoiceField(
        queryset=Division.objects.all(),
        required=False,
        label="Division",
        widget=forms.Select(attrs={'class': 'form-select rounded-3 shadow-sm'})
    )
    is_xpredict = forms.BooleanField(
        required=False,
        label="Is Xpredict Zone",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    contact_number = forms.CharField(
        required=False,
        label="Contact Number",
        widget=forms.TextInput(attrs={'class': 'form-control rounded-3 shadow-sm'})
    )
    date_of_birth = forms.DateField(
        required=False,
        label="Date of Birth",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control rounded-3 shadow-sm'})
    )
    profile_picture = forms.ImageField(
        required=False,
        label="Profile Picture",
        widget=forms.FileInput(attrs={'class': 'form-control rounded-3 shadow-sm'})
    )

    class Meta:
        model = User
        fields = ['username', 'password', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            try:
                profile = self.instance.userprofile
                self.fields['zone'].initial = profile.zone
                self.fields['division'].initial = profile.division
                self.fields['is_xpredict'].initial = profile.is_xpredict
                self.fields['contact_number'].initial = profile.contact_number
                self.fields['date_of_birth'].initial = profile.date_of_birth
            except UserProfile.DoesNotExist:
                pass
        else:
            self.fields['password'].required = True

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.zone = self.cleaned_data.get('zone')
            profile.division = self.cleaned_data.get('division')
            profile.is_xpredict = self.cleaned_data.get('is_xpredict', False)
            if self.cleaned_data.get('contact_number') is not None:
                profile.contact_number = self.cleaned_data.get('contact_number')
            if self.cleaned_data.get('date_of_birth'):
                profile.date_of_birth = self.cleaned_data.get('date_of_birth')
            if self.cleaned_data.get('profile_picture'):
                profile.profile_picture = self.cleaned_data.get('profile_picture')
            if user.email:
                profile.email = user.email
            profile.save()
        return user

def master_dashboard(request):
    return render(request, 'xp/master/dashboard.html', {'master_models': MASTER_MODELS})

def master_list(request, app_label, model_name):
    info = get_master_model_info(app_label, model_name)
    if not info:
        messages.error(request, "Invalid master model.")
        return redirect('master_dashboard')
    
    ModelClass = apps.get_model(app_label, model_name)
    objects = ModelClass.objects.all()
    
    context = {
        'info': info,
        'objects': objects,
    }
    return render(request, 'xp/master/list.html', context)

def master_create(request, app_label, model_name):
    info = get_master_model_info(app_label, model_name)
    if not info:
        return redirect('master_dashboard')
        
    ModelClass = apps.get_model(app_label, model_name)
    
    if app_label == 'auth' and model_name == 'user':
        FormClass = UserMasterForm
    else:
        FormClass = modelform_factory(ModelClass, form=MasterModelForm, exclude=[])
        
    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, f"{info['name']} created successfully.")
            return redirect('master_list', app_label=app_label, model_name=model_name)
    else:
        form = FormClass()
        
    return render(request, 'xp/master/form.html', {'form': form, 'info': info, 'action': 'Create'})

def master_update(request, app_label, model_name, pk):
    info = get_master_model_info(app_label, model_name)
    if not info:
        return redirect('master_dashboard')
        
    ModelClass = apps.get_model(app_label, model_name)
    obj = get_object_or_404(ModelClass, pk=pk)
    
    if app_label == 'auth' and model_name == 'user':
        FormClass = UserMasterForm
        form_kwargs = {'instance': obj}
    else:
        FormClass = modelform_factory(ModelClass, form=MasterModelForm, exclude=[])
        form_kwargs = {'instance': obj}
        
    if request.method == 'POST':
        form = FormClass(request.POST, request.FILES, **form_kwargs)
        if form.is_valid():
            form.save()
            messages.success(request, f"{info['name']} updated successfully.")
            return redirect('master_list', app_label=app_label, model_name=model_name)
    else:
        form = FormClass(**form_kwargs)
        
    return render(request, 'xp/master/form.html', {'form': form, 'info': info, 'action': 'Update'})

def master_delete(request, app_label, model_name, pk):
    info = get_master_model_info(app_label, model_name)
    if not info:
        return redirect('master_dashboard')
        
    ModelClass = apps.get_model(app_label, model_name)
    obj = get_object_or_404(ModelClass, pk=pk)
    
    if request.method == 'POST':
        obj.delete()
        messages.success(request, f"{info['name']} deleted successfully.")
        return redirect('master_list', app_label=app_label, model_name=model_name)
        
    return render(request, 'xp/master/delete.html', {'obj': obj, 'info': info})
