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


@register.filter
def add_class(value, arg):
    """
    Adds a CSS class to a form field.
    Usage: {{ form.field_name|add_class:"my-class" }}
    """
    return value.as_widget(attrs={'class': arg})


@register.filter(name='split')
def split(value, arg):
    """Splits a string by a given separator (arg) or newlines if present."""
    if not value:
        return []
    val_str = str(value)
    if "\n" in val_str:
        return [s.strip() for s in val_str.split("\n") if s.strip()]
    return [s.strip() for s in val_str.split(arg) if s.strip()]


@register.simple_tag
def get_global_settings():
    try:
        return GlobalSettings.objects.first()
    except Exception:
        return None