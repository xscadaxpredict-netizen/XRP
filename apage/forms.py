from django import forms
from .models import GeneralReport

class GeneralReportForm(forms.ModelForm):
    class Meta:
        model = GeneralReport
        fields = ['site', 'date_of_visit', 'point1', 'point2', 'point3', 'point4', 'notes', 'attachment']
        widgets = {
            'date_of_visit': forms.DateInput(attrs={'type': 'date'}),
        }

from django import forms

class ClientSignatureForm(forms.Form):
    client_name = forms.CharField(max_length=255, label='Client Name')
    client_signature = forms.CharField(widget=forms.HiddenInput())  # base64 string

from .models import BikeMaintenance
from django.contrib.auth.models import User

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class BikeMaintenanceForm(forms.ModelForm):
    tagged_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.SelectMultiple(attrs={'class': 'form-select select2', 'data-placeholder': 'Select users to tag...'}),
        required=False
    )
    oil_change_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False
    )
    last_oil_change_or_service_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'readonly': 'readonly'}),
        required=False
    )

    class Meta:
        model = BikeMaintenance
        fields = [
            'bike', 'last_oil_change_or_service_date', 'last_oil_change_km',
            'oil_change_date', 'current_mileage', 
            'brakes_ok', 'tires_ok', 'lights_ok', 
            'issues_faced', 'tagged_users'
        ]
        widgets = {
            'bike': forms.Select(attrs={'class': 'form-control'}),
            'last_oil_change_km': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'current_mileage': forms.NumberInput(attrs={'class': 'form-control'}),
            'brakes_ok': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'tires_ok': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'lights_ok': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'issues_faced': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
