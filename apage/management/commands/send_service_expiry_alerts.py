import ssl
# Bypass macOS SSL certificate verification issue
ssl.create_default_context = ssl._create_unverified_context

from django.core.management.base import BaseCommand
from django.utils import timezone
from apage.models import ServiceExpiry
from django.core.mail import send_mail
from django.conf import settings

class Command(BaseCommand):
    help = 'Send email alerts to respective persons for expired services'

    def handle(self, *args, **options):
        from datetime import timedelta
        today = timezone.localdate()
        expiry_limit = today + timedelta(days=7)

        # Find all expiries that expire in 7 days or less, and haven't been notified today
        pending_expiries = ServiceExpiry.objects.filter(
            expiry_date__lte=expiry_limit
        ).exclude(
            last_notified_date=today
        )

        sent_count = 0
        for expiry in pending_expiries:
            days_left = (expiry.expiry_date - today).days

            if days_left > 0:
                time_status = f"expires in {days_left} days (on {expiry.expiry_date.strftime('%d %b %Y')})"
            elif days_left == 0:
                time_status = f"expires today (on {expiry.expiry_date.strftime('%d %b %Y')})"
            else:
                time_status = f"expired on {expiry.expiry_date.strftime('%d %b %Y')} ({abs(days_left)} days ago)"

            subject = f"Alert: Service Expiry Notification - {expiry.service.name}"
            message = (
                f"Hello,\n\n"
                f"This is an automated notification to inform you that the service "
                f"'{expiry.service.name}' {time_status}.\n\n"
                f"Please take the necessary action to renew or update it.\n\n"
                f"Best regards,\n"
                f"System Admin"
            )
            try:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL or 'xpredictdigitalcontrols@gmail.com',
                    recipient_list=[expiry.email],
                    fail_silently=False,
                )
                expiry.notified = True
                expiry.last_notified_date = today
                expiry.save(update_fields=['notified', 'last_notified_date'])
                self.stdout.write(self.style.SUCCESS(
                    f"Successfully sent expiry email to {expiry.email} for service '{expiry.service.name}'"
                ))
                sent_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f"Failed to send email to {expiry.email} for service '{expiry.service.name}': {str(e)}"
                ))

        self.stdout.write(self.style.SUCCESS(
            f"Processed service expiry email notifications. Total sent: {sent_count}"
        ))
