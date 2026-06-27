from django import template
from website.models import GlobalSettings

register = template.Library()

@register.simple_tag
def get_global_settings():
    try:
        return GlobalSettings.objects.first()
    except:
        return None
