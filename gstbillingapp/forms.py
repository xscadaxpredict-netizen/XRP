from django.forms import ModelForm
from .models import Customer
from .models import Product
from .models import UserProfile



class CustomerForm(ModelForm):
     def __init__(self, *args, **kwargs):
          super(CustomerForm, self).__init__(*args, **kwargs)
          for field_name, field in self.fields.items():
               field.widget.attrs['class'] = 'form-control'
               
     class Meta:
          model = Customer
          fields = ['customer_name', 'customer_address', 'customer_phone', 'customer_gst','customer_pan']


class ProductForm(ModelForm):
     def __init__(self, *args, **kwargs):
          super(ProductForm, self).__init__(*args, **kwargs)
          for field_name, field in self.fields.items():
               field.widget.attrs['class'] = 'form-control'
               
     class Meta:
          model = Product
          fields = ['product_name', 'product_hsn', 'product_unit', 'product_gst_percentage', 'product_rate_with_gst']


class UserProfileForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(UserProfileForm, self).__init__(*args, **kwargs)
        self.fields['business_title'].required = True
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

    class Meta:
        model = UserProfile
        fields = ['business_title', 'business_address', 'business_email', 'business_phone', 'business_gst']
