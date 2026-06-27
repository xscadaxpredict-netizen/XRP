from django import template
from app.models import SubModuleVisibility
from website.models import GlobalSettings

register = template.Library()

@register.filter
def is_submodule_visible(user, submodule):
    try:
        visibility = SubModuleVisibility.objects.get(user=user, submodule=submodule)
        return visibility.is_visible
    except SubModuleVisibility.DoesNotExist:
        return False

@register.filter(name='split')
def split(value, arg):
    """Splits a string by a given separator (arg)."""
    return value.split(arg)

@register.filter
def add_class(value, arg):
    """
    Adds a CSS class to a form field.
    Usage: {{ form.field_name|add_class:"my-class" }}
    """
    return value.as_widget(attrs={'class': arg})

@register.simple_tag
def get_global_settings():
    try:
        return GlobalSettings.objects.first()
    except:
        return None