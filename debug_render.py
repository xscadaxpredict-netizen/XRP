import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xplbs.settings')
django.setup()
from django.test import Client
from django.contrib.auth.models import User

user = User.objects.get(username='shashank')
c = Client()
c.force_login(user)
response = c.get('/xshot/invoice/6/')
with open('debug.html', 'w', encoding='utf-8') as f:
    f.write(response.content.decode('utf-8'))
