from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apage.models import SiteAMC
from website.models import Notification
from django.contrib.auth.models import User
from django.db import models

class Command(BaseCommand):
    help = 'Check for expiring AMCs and notify admins'

    def handle(self, *args, **kwargs):
        today = timezone.now().date()
        expiry_limit = today + timedelta(days=7)
        
        # Find AMCs expiring in the next 7 days
        expiring_amcs = SiteAMC.objects.filter(
            has_amc=True,
            amc_end_date__gte=today,
            amc_end_date__lte=expiry_limit
        )
        
        # Target staff and superusers
        admins = User.objects.filter(models.Q(is_staff=True) | models.Q(is_superuser=True)).distinct()
        
        if not expiring_amcs.exists():
            self.stdout.write(self.style.NOTICE("No AMCs expiring within the next 7 days."))
            return

        for amc in expiring_amcs:
            days_left = (amc.amc_end_date - today).days
            title = f"AMC Expiry Alert: {amc.site.name}"
            message = f"The AMC for {amc.site.name} is expiring on {amc.amc_end_date} ({days_left} days left). Please renew it."
            
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title=title,
                    message=message
                )
                self.stdout.write(self.style.SUCCESS(f"Notified {admin.username} about {amc.site.name}"))
