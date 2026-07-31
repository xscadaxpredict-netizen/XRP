



# ---------------------------------------Module Visibility --------------------------------------------------------------------------------------

from django import forms
from .models import ModuleVisibility, CoreModule

class ModuleVisibilityForm(forms.ModelForm):
    class Meta:
        model = ModuleVisibility
        fields = [ 'enabled_modules']

    enabled_modules = forms.ModelMultipleChoiceField(
        queryset=CoreModule.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input cursor-pointer'}),
        required=False
    )


