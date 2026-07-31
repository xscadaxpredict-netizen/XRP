from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal

class AdvanceGroup(models.Model):
    name = models.CharField(max_length=255)
    total_advance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paid_overdue = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    used_advance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(default=timezone.now)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_closed = models.BooleanField(default=False)
    leader = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="led_advance_groups")
    payment_mode = models.CharField(max_length=50,
    choices=[
        ("cash", "Cash"),
        ("upi", "UPI"),
        ("net_banking", "Net Banking"),
        ("cheque", "Cheque"),
        ("other", "Other"),
    ],
    default="net_banking",
)
    
    # New Site tracking fields
    site = models.ForeignKey('apage.Site', on_delete=models.SET_NULL, null=True, blank=True, related_name="advance_groups")
    advance_type = models.CharField(
        max_length=50,
        choices=[
            ('Site AMC', 'Site AMC'),
            ('Site Project', 'Site Project'),
            ('Office Maintenance', 'Office Maintenance'),
            ('Food and Groceries', 'Food and Groceries'),
            ('Client Visit', 'Client Visit'),
        ],
        null=True,
        blank=True
    )


    def __str__(self):
        leader_name = self.leader.get_full_name() if self.leader else "No Leader"
        return f"{self.name} (Leader: {leader_name})"

    def get_calculated_used_advance(self):
        """Calculates what the used_advance SHOULD be, without saving."""
        used = self.expense_set.filter(
            item_type="advances",
            is_rejected=False,
            is_draft=False,
            is_allocation=False
        ).exclude(status='rejected').aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        return used

    def recalculate_balance(self):
        """Calculates and saves the new balance including adjustments."""
        used = self.get_calculated_used_advance()
        adjustments = self.adjustments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        self.used_advance = used
        self.remaining_balance = max((self.total_advance + self.paid_overdue) - (used + adjustments), Decimal("0.00"))
        self.save(update_fields=["used_advance", "remaining_balance"])
        return self.remaining_balance


class AdvanceAdjustment(models.Model):
    ADJUSTMENT_TYPES = [
        ('salary', 'Salary Deduction'),
        ('cash', 'Cash Return'),
        ('credit_note', 'Credit Note / Adjustment'),
    ]
    group = models.ForeignKey(AdvanceGroup, on_delete=models.CASCADE, related_name="adjustments", null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="standalone_adjustments", null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    adjustment_type = models.CharField(max_length=20, choices=ADJUSTMENT_TYPES, default='credit_note')
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    is_used = models.BooleanField(default=False)
    attached_group = models.ForeignKey(AdvanceGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="attached_credit_notes")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.group:
            new_balance = self.group.recalculate_balance()
            self.group.is_closed = (new_balance <= 0)
            self.group.save(update_fields=["is_closed"])

    def __str__(self):
        group_name = self.group.name if self.group else (self.user.username if self.user else "Standalone")
        return f"{self.get_adjustment_type_display()} for {group_name} - ₹{self.amount}"


class AdvanceAssignment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    group = models.ForeignKey(AdvanceGroup, on_delete=models.CASCADE)
    is_leader = models.BooleanField(default=False)  # ✅ New field

    class Meta:
        unique_together = ('user', 'group')

    def __str__(self):
        role = " (Leader)" if self.is_leader else ""
        return f"{self.user.username} - {self.group.name}{role}"

class Expense(models.Model):
    ITEM_TYPES = [
        ('fright_transportation', 'Fright/Transportation'),
        ('food_grocery', 'Food/Grocery'),
        ('fuel_oil', 'Fuel and Oil'),
        ('others', 'Others'),
        ('vendor', 'Vendor'),
        ('reimbursement', 'Reimbursement'),
        ('site_services', 'Site Services'),
        ('advances', 'Advances'),
        ('travelling', 'Travelling'),
        ('electricity_bill', 'Electricity Bill'),
        ('internet_bill', 'Internet Bill'),
        ('postage_telegram', 'Postage and Telegram'),
        ('machine_repair', 'Machine Repair and Maintenance'),
        ('conveyance', 'Conveyance'),
        ('stationary_printing', 'Stationary and Printing'),
        ('hospitality', 'Hospitality'),
        ('medicine', 'Medicine'),
    ]

    TRANSACTION_CATEGORY_CHOICES = [
        ('internal', 'Internal'),
        ('external', 'External'),
    ]
    
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('net_banking', 'Net Banking'),
        ('debit_card', 'Debit Card'),
        ('credit_card', 'Credit Card'),
    ]

    PAYMENT_OPTIONS = [
    ('bill', 'Bill'),
    ('voucher', 'Voucher'),
    ('gst', 'GST'),
     ('2_wheeler', '2-Wheeler'),
    ('4_wheeler', '4-Wheeler'),
]

    # Model fields
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_expenses', null=True, blank=True)
    item_type = models.CharField(max_length=50, choices=ITEM_TYPES, blank=True, null=True)
    item_name = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateField(auto_now_add=True)
    transaction_option = models.CharField(max_length=20, choices=PAYMENT_OPTIONS, null=True)
    bill_photo = models.FileField(upload_to='bills/', blank=True, null=True)
    voucher_number = models.CharField(max_length=100, blank=True, null=True)
    transaction_category = models.CharField(max_length=100, choices=TRANSACTION_CATEGORY_CHOICES, blank=True, null=True)
    internal_option = models.CharField(max_length=100, null=True, blank=True, default='abs')
    external_type = models.CharField(max_length=100, null=True, blank=True, default='legs')
    gst_photo = models.ImageField(upload_to='gst_photos/', null=True, blank=True)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE_CHOICES, blank=True, null=True)
    proof_photo = models.FileField(upload_to='proofs/', blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    transaction_details = models.TextField(null=True, blank=True)
    evoucher_number = models.CharField(max_length=100, blank=True, null=True)
    transaction_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('paid', 'Paid'), ('rejected', 'Rejected')], default='pending')
    is_draft = models.BooleanField(default=False)
    advance_group = models.ForeignKey('AdvanceGroup', on_delete=models.SET_NULL, null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True, default='NONE')
    is_approved = models.BooleanField(default=False)
    is_rejected = models.BooleanField(default=False)
    
    km = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Kilometers field
    from_location = models.CharField(max_length=255, blank=True, null=True)
    to_location = models.CharField(max_length=255, blank=True, null=True)
    calculated_km = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    conveyance = models.ForeignKey('Conveyance', on_delete=models.SET_NULL, null=True, blank=True)  # Use string for Conveyance
    delete_requested = models.BooleanField(default=False)
    is_allocation = models.BooleanField(default=False)


    # Method to calculate the amount based on km and vehicle type
    def calculate_amount(self):
        if self.conveyance and self.km is not None:
            return self.conveyance.price_per_km * self.km
        return None  # Return None if no calculation is required

    # Override save method to calculate amount conditionally
    def save(self, *args, **kwargs):
        # Only calculate amount if it's a conveyance type and no amount was manually assigned
        if self.item_type == 'conveyance' and self.conveyance and self.km is not None:
            self.amount = self.calculate_amount()
        super().save(*args, **kwargs)

    # Display format for the model instance
    def __str__(self):
        return f"{self.created_by} - {self.item_type} - {self.evoucher_number}"


# BorrowedAmount Model
class BorrowedAmount(models.Model):

    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='borrowed_amounts')
    borrowed_from = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.borrowed_from} - {self.amount}"
    
# models.py
class AdvanceGroupUpdateLog(models.Model):
    group = models.ForeignKey(AdvanceGroup, on_delete=models.CASCADE, related_name='update_logs')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    previous_amount = models.DecimalField(max_digits=10, decimal_places=2)
    new_amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    proof_file = models.FileField(upload_to='advance_proofs/', null=True, blank=True)
    remarks = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.group.name} updated by {self.updated_by} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

# CashVoucher Model
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class CashVoucher(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, null=True, blank=True,related_name='cash_vouchers')
    voucher_number = models.CharField(max_length=20, unique=True)
    date = models.DateField(auto_now_add=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    paid_to = models.CharField(max_length=25)
    item_name = models.CharField(max_length=255)
    transaction_date = models.DateField(null=True, blank=True)
    verified_by = models.CharField(max_length=255, null=True, blank=True)
    approved_by = models.CharField(max_length=255, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_cash_vouchers', null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True, default='NONE')
    verified_at = models.DateTimeField(default=timezone.now, null=True, blank=True)  # Use timezone.now()
    proof_photo = models.FileField(upload_to='cashvoucher_proofs/', null=True, blank=True)

    

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"Voucher #{self.voucher_number} - {self.status}"



from django.db import models
from django.conf import settings  # For referencing the custom user model

class Payment(models.Model):
    paid_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments")
    transaction_id = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    from_date = models.DateField()  # Start date for the payment duration
    to_date = models.DateField()    # End date for the payment duration
    screenshot = models.ImageField(upload_to='payment_screenshots/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    remarks = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.paid_to} - {self.transaction_id}"
    

# models.py


# Check if the import is necessary and valid

# website/models.py

# website/models.py

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=[('unread', 'Unread'), ('read', 'Read')], default='unread')

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Notification)
def trigger_push_notification(sender, instance, created, **kwargs):
    if created:
        from .fcm_push import send_push_notification
        try:
            send_push_notification(instance.user, instance.title, instance.message)
        except Exception as e:
            print(f"FCM Error: {e}")


class FCMToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created = models.DateTimeField(auto_now_add=True)




from django.db import models

class Conveyance(models.Model):
    VEHICLE_TYPES = [
        ('2_wheeler', '2_Wheeler'),
        ('4_wheeler', '4_Wheeler'),
    ]
    
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_TYPES)
    price_per_km = models.DecimalField(max_digits=10, decimal_places=2)  # Price per kilometer

    def __str__(self):
        return f"{self.vehicle_type} - {self.price_per_km} per km"

class ConveyanceSite(models.Model):
    site_name = models.CharField(max_length=255)
    kilometers = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.site_name} ({self.kilometers} km)"

from django.db import models
from django.contrib.auth.models import User

class AdvancePayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount}"
    


class ProofPhoto(models.Model):
    expense = models.ForeignKey(Expense, related_name='proof_photos', on_delete=models.CASCADE)
    file = models.FileField(upload_to='proofs/')




from django.db import models
from django.contrib.auth.models import User

class PaymentRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} "

class PaymentRequestMessage(models.Model):
    request = models.ForeignKey(PaymentRequest, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField(null=True,blank=True)
    attachment = models.FileField(upload_to='attachments/', blank=True, null=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username} - {self.message[:30]}"
        
    @property
    def is_gif(self):
        return bool(self.message and self.message.startswith('[GIF] '))
        
    @property
    def gif_url(self):
        if self.is_gif:
            url = self.message.replace('[GIF] ', '')
            # Convert any Tenor static format to MP4 animated
            if 'media.tenor.com' in url:
                import re
                url = re.sub(r'AAAA[A-Z0-9]/', 'AAAP1/', url)
                url = re.sub(r'\.(gif|webp)$', '.mp4', url)
            return url
        return None
    



class DirectPay(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    e_voucher_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    item_type = models.CharField(max_length=50, choices=Expense.ITEM_TYPES)
    item_name = models.CharField(max_length=255)
    payment_category = models.CharField(max_length=20, choices=Expense.PAYMENT_OPTIONS)
    transaction_category = models.CharField(max_length=20, choices=Expense.TRANSACTION_CATEGORY_CHOICES)
    external_name = models.CharField(max_length=255, null=True, blank=True)
    bill_file = models.FileField(upload_to="directpay/bills/", null=True, blank=True)
    gst_file = models.FileField(upload_to="directpay/gst/", null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=Expense.PAYMENT_MODE_CHOICES)
    proof_photo = models.FileField(upload_to="directpay/proofs/", null=True, blank=True)
    transaction_date = models.DateField()
    status = models.CharField(max_length=20, default="draft")  # draft / completed
    delete_request = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"DirectPay {self.e_voucher_number} ({self.status})"
    


class MobileSession(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=128, unique=True)
    created = models.DateTimeField(auto_now_add=True)

class GlobalSettings(models.Model):
    restrict_transaction_date = models.BooleanField(
        default=True,
        help_text="If checked, restricts transaction date to prevent future and old past dates."
    )

    class Meta:
        verbose_name = "Global Setting"
        verbose_name_plural = "Global Settings"

    def __str__(self):
        return "Global Settings"

    def save(self, *args, **kwargs):
        if not self.pk and GlobalSettings.objects.exists():
            return
        super().save(*args, **kwargs)


class Holiday(models.Model):
    name = models.CharField(max_length=255)
    date = models.DateField()

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"{self.name} - {self.date}"

class TodoItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='todo_items')
    title = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {'Completed' if self.is_completed else 'Pending'}"

class CalendarEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calendar_events')
    title = models.CharField(max_length=255)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=True)
    color = models.CharField(max_length=50, default='#3788d8') # Adding a color field for premium styling

    def __str__(self):
        return f"{self.title} ({self.start_date.date()})"