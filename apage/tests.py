from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.core import mail
from django.core.management import call_command
from apage.models import Service, ServiceExpiry

class ServiceExpiryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Client()
        self.client.login(username='testuser', password='password')
        self.service = Service.objects.create(name='Test Cleaning Service')

    def test_service_expiry_creation(self):
        expiry = ServiceExpiry.objects.create(
            service=self.service,
            expiry_date=timezone.localdate() + timedelta(days=5),
            email='test@example.com'
        )
        self.assertEqual(str(expiry.service), 'Test Cleaning Service')
        self.assertEqual(expiry.email, 'test@example.com')
        self.assertFalse(expiry.notified)

    def test_management_command_sends_email(self):
        # Create an expired service expiry (expires in 6 days, i.e. within 7 days window)
        expiring_soon = ServiceExpiry.objects.create(
            service=self.service,
            expiry_date=timezone.localdate() + timedelta(days=6),
            email='soon@example.com'
        )
        # Create a future service expiry (expires in 10 days, i.e. outside 7 days window)
        expiring_far = ServiceExpiry.objects.create(
            service=self.service,
            expiry_date=timezone.localdate() + timedelta(days=10),
            email='far@example.com'
        )

        # Call management command first time
        call_command('send_service_expiry_alerts')

        # Verify only 1 email was sent (to soon@example.com)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['soon@example.com'])
        self.assertIn('Test Cleaning Service', mail.outbox[0].subject)

        # Verify last_notified_date is updated
        expiring_soon.refresh_from_db()
        self.assertEqual(expiring_soon.last_notified_date, timezone.localdate())

        # Call command again on the same day: it should NOT duplicate the email
        call_command('send_service_expiry_alerts')
        self.assertEqual(len(mail.outbox), 1) # Still 1 total email in outbox

        # Now simulate updating the expiry date (moving it to 30 days in the future)
        expiring_soon.expiry_date = timezone.localdate() + timedelta(days=30)
        # Reset last_notified_date to a past date to simulate a new day
        expiring_soon.last_notified_date = timezone.localdate() - timedelta(days=1)
        expiring_soon.save()

        # Call command again (simulating a new day): it should NOT notify anymore because it is now far in the future
        call_command('send_service_expiry_alerts')
        self.assertEqual(len(mail.outbox), 1) # Still 1 total email in outbox

    def test_views_access(self):
        response = self.client.get(reverse('service_expiry_management'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'apage/service_expiry.html')

    def test_views_post_create(self):
        response = self.client.post(reverse('service_expiry_management'), {
            'service_name': 'New Dynamic Service',
            'expiry_date': '2026-07-04',
            'email': 'newservice@example.com'
        })
        self.assertEqual(response.status_code, 302) # Redirects back
        self.assertTrue(Service.objects.filter(name='New Dynamic Service').exists())
        self.assertTrue(ServiceExpiry.objects.filter(email='newservice@example.com').exists())

class GetSitesAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='api_testuser', password='password')
        self.client = Client()

    def test_get_sites_requires_authentication(self):
        response = self.client.get(reverse('get_sites'))
        self.assertEqual(response.status_code, 401)

    def test_get_sites_with_session_authentication(self):
        self.client.login(username='api_testuser', password='password')
        response = self.client.get(reverse('get_sites'))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)


class PDFDownloadTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from apage.models import MOM, Site, GeneralReport, Machine, MaintenanceChecklist, State, ServiceReport
        import datetime

        self.user = User.objects.create_user(username='testpdfuser', password='password')
        self.client = Client()
        self.client.login(username='testpdfuser', password='password')

        # Create Site
        self.site = Site.objects.create(name='Test Site')

        # Create State
        self.state = State.objects.create(name='Test State')

        # Create Machine
        self.machine = Machine.objects.create(name='Test Machine')

        # Create MOM record
        self.mom = MOM.objects.create(
            topic='Test Topic',
            organize='Test Organizer',
            meeting_chair='Test Chair',
            location='Test Location',
            date=datetime.date.today(),
            start_time=datetime.time(10, 0, 0),
            end_time=datetime.time(11, 0, 0),
            updated_by='testpdfuser',
            meeting_conclusion='Test Conclusion',
            summary_of_discussion='Test Summary',
            created_by=self.user
        )

        # Create GeneralReport record
        self.report = GeneralReport.objects.create(
            site=self.site,
            date_of_visit=datetime.date.today(),
            point1='P1',
            point2='P2',
            point3='P3',
            point4='P4',
            notes='Notes',
            created_by=self.user
        )

        # Create MaintenanceChecklist record
        self.checklist = MaintenanceChecklist.objects.create(
            inspector_name='testpdfuser',
            date=datetime.date.today(),
            machine=self.machine,
            visit_date=datetime.date.today(),
            created_by=self.user,
            supply_voltage='checked',
            current_load='checked',
            observations='Ok'
        )

        # Create ServiceReport record
        self.service_report = ServiceReport.objects.create(
            service_name='Test Service',
            date_of_visit=datetime.date.today(),
            customer_name='Test Customer',
            state=self.state,
            created_by=self.user
        )

    def test_pdf_mom_download(self):
        response = self.client.get(reverse('pdf_mom', kwargs={'mom_id': self.mom.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)

    def test_pdf_maintenance_checklist_download(self):
        response = self.client.get(reverse('pdf_maintenance_checklist', kwargs={'checklist_id': self.checklist.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)

    def test_pdf_general_report_download(self):
        response = self.client.get(reverse('generate_report_pdf', kwargs={'report_id': self.report.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)

    def test_pdf_service_report_download(self):
        response = self.client.get(reverse('service_report_pdf', kwargs={'pk': self.service_report.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(len(response.content) > 0)

