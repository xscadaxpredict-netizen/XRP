# from django.contrib import admin

# from .models import Enquiry,Products,Executive

# # Register your models here.
# admin.site.register(Enquiry)
# admin.site.register(Products)
# admin.site.register(Executive)
from django.contrib import admin
from django.apps import apps

# Get the current app's config
app_config = apps.get_app_config('indent')  # Change 'indent' to your app name if different

# Loop through all models and register if not already registered
for model_name, model in app_config.models.items():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass