from django import template

register = template.Library()


@register.filter
def add_class(value, arg):
    """
    Adds a CSS class to a form field.
    Usage: {{ form.field_name|add_class:"my-class" }}
    """
    return value.as_widget(attrs={'class': arg})
