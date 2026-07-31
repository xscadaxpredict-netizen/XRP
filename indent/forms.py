from django import forms
from django.forms import inlineformset_factory, modelformset_factory
from .models import Indent, IndentItem, PurchaseOrder, PurchaseItem, Snag, Vendor

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def to_python(self, data):
        if not data:
            return None

        if isinstance(data, list):
            return [super(MultipleFileField, self).to_python(item) for item in data]
        
        return super(MultipleFileField, self).to_python(data)

    def clean(self, data, initial=None):
        if not data and self.required:
             raise forms.ValidationError(self.error_messages['required'])
        return data

class IndentForm(forms.ModelForm):
    class Meta:
        model = Indent
        fields = ['title', 'quantity', 'requested_by', 'remarks','department']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Indent title'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Quantity'}),
            'requested_by': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Requested by'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Remarks'}),
        }

IndentItemFormSet = inlineformset_factory(
    Indent,
    IndentItem,
    fields=['product_name', 'quantity', 'remarks'],
    widgets={
        'product_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product name'}),
        'quantity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Quantity'}),
        'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Remarks'}),
    },
    extra=1,
    can_delete=True
)

from django import forms
from .models import PurchaseOrder, Vendor

class PurchaseOrderForm(forms.ModelForm):
    vendor_name = forms.CharField(
        max_length=100,
        required=True,
        label="Vendor Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'})
    )
    vendor_code = forms.CharField(
        required=False,
        disabled=True,
        label="Vendor Code",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    attachments = MultipleFileField(
        widget=MultipleFileInput(attrs={'class': 'form-control', 'multiple': True}),
        required=False,
        label="Proforma Invoices (Multiple)"
    )

    class Meta:
        model = PurchaseOrder
        fields = ['po_number', 'expected_delivery', 'last_bought_value', 'payment_terms']
        widgets = {
            'expected_delivery': forms.DateInput(
                attrs={
                    'type': 'date',        # ← THIS shows the calendar picker
                    'class': 'form-control'
                }
            ),
            'last_bought_value': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Optional Last Bought Value'}),
            'payment_terms': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['po_number'].required = False
        
        # Make payment_terms not required so it defaults gracefully
        if 'payment_terms' in self.fields:
            self.fields['payment_terms'].required = False
            self.fields['payment_terms'].empty_label = None
            choices = self.fields['payment_terms'].choices
            self.fields['payment_terms'].choices = [c for c in choices if c[0]]
            
        if self.instance and self.instance.pk and self.instance.vendor:
            self.fields['vendor_name'].initial = self.instance.vendor.name
            self.fields['vendor_code'].initial = self.instance.vendor.code

    def clean_payment_terms(self):
        val = self.cleaned_data.get('payment_terms')
        if not val:
            return 'Credit'
        return val

    def clean_po_number(self):
        val = self.cleaned_data.get('po_number')
        if not val:
            return 'TEMP-PO-NUM'
        return val

    def save(self, commit=True):
        po = super().save(commit=False)
        vendor_name = self.cleaned_data['vendor_name'].strip()

        # Find vendor or create
        vendor = Vendor.objects.filter(name__iexact=vendor_name).first()
        if not vendor:
            last_vendor = Vendor.objects.order_by('-id').first()
            next_number = (last_vendor.id + 1) if last_vendor else 1
            vendor_code = f"V{next_number:04d}"
            vendor = Vendor.objects.create(name=vendor_name, code=vendor_code)

        po.vendor = vendor
        if commit:
            po.save()
        return po
    
class PurchaseItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = ['product_name', 'quantity', 'unit_price', 'remarks']
        widgets = {
            'product_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product name'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Quantity'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Unit price'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Remarks'}),
        }

# Formset to handle purchase items
PurchaseItemFormSet = modelformset_factory(
    PurchaseItem,
    form=PurchaseItemForm,
    extra=0,           # dynamically controlled in view
    can_delete=False
)

# from django import forms

# class DelayReasonForm(forms.ModelForm):
#     class Meta:
#         model = PurchaseOrder
#         fields = ['delivery_delay_reason']


from django import forms
from .models import PurchaseOrder

class DelayReasonForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['delivery_delay_reason']
        widgets = {
            'delivery_delay_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter delay reason here...'
            }),
        }


from django import forms
from .models import Vendor

class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ['name', 'level', 'contact_email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


from django import forms
from .models import MaterialIssue, QCCheck, TelemetryRecord, Delivery


class MaterialIssueForm(forms.ModelForm):
    class Meta:
        model = MaterialIssue
        fields = ["stock_item", "issued_qty", "unit_price"]
        widgets = {
            "stock_item": forms.Select(attrs={"class": "form-select"}),
            "issued_qty": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "unit_price": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01"}),
        }
    
    def _post_clean(self):
        # Call parent to populate instance, but catch the validation error
        # since project/production_order will be set in the view
        try:
            super()._post_clean()
        except forms.ValidationError:
            # Ignore validation errors from model.clean()
            # The view will set project before saving
            pass

from django import forms
from .models import QCCheck, Snag

class QCCheckForm(forms.ModelForm):
    class Meta:
        model = QCCheck
        fields = ["production_order", "passed", "remarks"]
        widgets = {
            "passed": forms.Select(
                choices=[(True, "Pass"), (False, "Fail")],
                attrs={"class": "form-select"}
            ),
            "remarks": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Default to Pass
        if not self.instance.pk:
            self.fields["passed"].initial = True

class SnagReportForm(forms.ModelForm):
    class Meta:
        model = Snag
        fields = ["production_order", "snap_type", "description"]

# Inline Snag form for QC fail (exclude production_order, set dynamically in view)
class SnagInlineForm(forms.ModelForm):
    class Meta:
        model = Snag
        fields = ["snap_type", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove HTML5 required attribute; we will enforce in view
        self.fields['snap_type'].required = False
        self.fields['description'].required = False

class TelemetryRecordForm(forms.ModelForm):
    class Meta:
        model = TelemetryRecord
        fields = ["production_order", "data"]
        widgets = {
            "data": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

class DeliveryForm(forms.ModelForm):
    class Meta:
        model = Delivery
        fields = ["production_order", "delivered_at", "remarks"]
        widgets = {
            "delivered_at": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "remarks": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }




from django import forms
from .models import Project
from django.contrib.auth.models import User

class ProjectForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'assigned_users' in self.fields:
            self.fields['assigned_users'].queryset = User.objects.order_by('first_name', 'username')
            
        from Riva.models import Enquiry
        oc_numbers = Enquiry.objects.filter(is_confirmed=True).exclude(oc_number__isnull=True).exclude(oc_number__exact='').values_list('oc_number', flat=True)
        choices = [('', '---------')] + [(oc, oc) for oc in oc_numbers]
        self.fields['oc_number'].widget = forms.Select(choices=choices, attrs={'class': 'form-select'})

    class Meta:
        model = Project
        fields = [
            'name', 'delivery_date', 'plan_start', 'plan_end',
            'place', 'requirement', 'configuration', 'revenue',
            'oc_number', 'project_type', 'status', 'assigned_users', 'lead',
            'machine_kit', 'product'
        ]
        widgets = {
            'delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'plan_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'plan_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),

            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'place': forms.TextInput(attrs={'class': 'form-control'}),
            'requirement': forms.Textarea(attrs={'class': 'form-control'}),
            'configuration': forms.Textarea(attrs={'class': 'form-control'}),
            'revenue': forms.NumberInput(attrs={'class': 'form-control'}),
            'oc_number': forms.Select(attrs={'class': 'form-select'}),
            'project_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'lead': forms.Select(attrs={'class': 'form-select'}),
            'assigned_users': forms.SelectMultiple(attrs={'class': 'form-select', 'style': 'height: 150px;'}),
            'machine_kit': forms.Select(attrs={'class': 'form-select'}),
            'product': forms.Select(attrs={'class': 'form-select'}),
        }

from .models import Deployment, DeploymentImage

class DeploymentImageForm(forms.ModelForm):
    class Meta:
        model = DeploymentImage
        fields = ['image']
        widgets = {
            'image': MultipleFileInput(attrs={'class': 'form-control', 'multiple': True})
        }