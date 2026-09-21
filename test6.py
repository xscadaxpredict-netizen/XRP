import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xplbs.settings')
django.setup()
from django.test import Client
from django.contrib.auth.models import User

user = User.objects.get(username='shashank')
c = Client()
c.force_login(user)
res = c.get('/xshot/invoice/6')
content = res.content.decode('utf-8')

with open('rendered_invoice_final.html', 'w', encoding='utf-8') as f:
    f.write(content)
print('Rendered invoice saved to rendered_invoice_final.html')
