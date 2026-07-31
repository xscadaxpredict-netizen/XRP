from datetime import timedelta
from django.db import models
from django.db.models import Avg
from Riva.models import Products, Executive, FileUploadModel, Enquiry, RevertRemark, FollowUp

# Create your models here.
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL

import uuid
class Project(models.Model):
    PROJECT_TYPE_CHOICES = [
        ('OC', 'Work Order'),
        ('R&D', 'R&D'),
        ('INTERNAL', 'Internal Project'),
        ('MAINT', 'Office Maintenance'),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("delayed", "Delayed"),
        ("cancelled", "Cancelled"),
    ]

    name = models.CharField("Project Name", max_length=255)
    delivery_date = models.DateField("Delivery Date", null=True, blank=True)


    plan_start = models.DateField("Planned Start Date", null=True, blank=True)
    plan_end = models.DateField("Planned End Date", null=True, blank=True)

    place = models.CharField("Site Location", max_length=255, blank=True)
    requirement = models.TextField("Requirement", blank=True)
    configuration = models.TextField("Configuration", blank=True)
    revenue = models.DecimalField("Allocated Budget", max_digits=14, decimal_places=2, null=True, blank=True)

    oc_number = models.CharField("Work Order", max_length=128, blank=True)
    project_type = models.CharField("Project Type", max_length=16, choices=PROJECT_TYPE_CHOICES, default='R&D')

    lead = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='led_projects', verbose_name="Lead Department")

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_projects')
    created_at = models.DateTimeField("Created At", auto_now_add=True)
    updated_at = models.DateTimeField("Updated At", auto_now=True)
    
    assigned_users = models.ManyToManyField(User, blank=True, related_name='assigned_projects')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    client_token = models.UUIDField(default=uuid.uuid4, unique=True, null=True, blank=True)
    machine_kit = models.ForeignKey('MachineKit', on_delete=models.SET_NULL, null=True, blank=True, related_name='projects', verbose_name="Machine Kit (BOM)")
    product = models.ForeignKey(Products, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Product")

    class Meta:
        ordering = ['-created_at']
        permissions = [
            ("can_create_project", "Can create project"),
        ]

    def __str__(self):
        return f"{self.name} ({self.oc_number or self.project_type})"

    def save(self, *args, **kwargs):
        if self.oc_number and self.project_type != 'OC':
            self.project_type = 'OC'
        super().save(*args, **kwargs)

from django.db import models

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, blank=True, null=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='sub_departments'
    )
    assigned_users = models.ManyToManyField('auth.User', blank=True, related_name='assigned_departments')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Department"
        verbose_name_plural = "Departments"
    

class ProductionOrder(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("delayed", "Delayed"),
        ("cancelled", "Cancelled"),
    ]

    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name="production_orders")
    product = models.ForeignKey(Products, on_delete=models.CASCADE)
    # quantity = models.PositiveIntegerField()
    planned_start = models.DateField()
    planned_end = models.DateField()
    actual_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    # merge fields from second definition
    order_number = models.CharField(max_length=50, unique=True)
    sales_order = models.CharField(max_length=50, blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_production_orders")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    machine_kit = models.ForeignKey('MachineKit', on_delete=models.SET_NULL, null=True, blank=True, related_name="production_orders")

    def __str__(self):
        return f"PO-{self.order_number} ({self.product.name})"
    

from django.db import models
from django.db.models import Avg

class Vendor(models.Model):
    LEVEL_CHOICES = [
        ('L1', 'Level 1'),
        ('L2', 'Level 2'),
        ('L3', 'Level 3'),
        ('L4', 'Level 4'),
    ]

    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, blank=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    contact_number_2 = models.CharField(max_length=20, blank=True, null=True)

    # Tax & Bank Details
    gst_number = models.CharField(max_length=15, blank=True, null=True)
    pan_number = models.CharField(max_length=10, blank=True, null=True)
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    bank_account_no = models.CharField(max_length=30, blank=True, null=True)
    ifsc_code = models.CharField(max_length=11, blank=True, null=True)

    category = models.CharField(max_length=100, blank=True, null=True)  # Master will update this
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    credit_period_days = models.IntegerField("Credit Period (Days)", default=30)
    
    # Automated Ratings
    auto_delivery_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    auto_quality_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)
    auto_pricing_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.0)

    def update_automated_ratings(self):
        """Calculate and update automated ratings based on PO, GRN, and Pricing data."""
        from django.db.models import Avg
        
        # 1. Delivery Rating (🚚)
        pos = self.purchaseorder_set.filter(status__in=['received', 'partially_received'], expected_delivery__isnull=False)
        delivery_scores = []
        for po in pos:
            last_grn = po.grns.order_by('received_date').last()
            if last_grn:
                delay = (last_grn.received_date - po.expected_delivery).days
                if delay <= 0:
                    score = 5.0
                else:
                    # Penalty of 0.5 stars per day late, minimum 1.0 star
                    score = max(5.0 - (delay * 0.5), 1.0)
                delivery_scores.append(score)
        self.auto_delivery_rating = sum(delivery_scores) / len(delivery_scores) if delivery_scores else 0.0

        # 2. Quality Rating (📦)
        # Using a related_name if defined, or default purchaseorder_set
        grn_items = []
        for po in self.purchaseorder_set.all():
            for grn in po.grns.all():
                grn_items.extend(grn.items.all())
        
        if grn_items:
            total_received = sum(item.received_quantity for item in grn_items)
            total_accepted = sum(item.accepted_qty for item in grn_items)
            if total_received > 0:
                self.auto_quality_rating = (total_accepted / total_received) * 5.0
            else:
                self.auto_quality_rating = 0.0
        else:
            self.auto_quality_rating = 0.0

        # 3. Pricing Rating (💰)
        # Compare vendor's unit price with average system price for same product names
        pricing_scores = []
        from .models import PurchaseItem
        vendor_items = PurchaseItem.objects.filter(po__vendor=self)
        for item in vendor_items:
            # Get average price from OTHER vendors for the same product
            avg_peer_price = PurchaseItem.objects.filter(
                product_name=item.product_name
            ).exclude(po__vendor=self).aggregate(Avg('unit_price'))['unit_price__avg']
            
            if avg_peer_price and item.unit_price > 0:
                # If vendor price is lower than or equal to average, 5 stars
                # If higher, reduce score proportionally
                ratio = float(avg_peer_price) / float(item.unit_price)
                score = min(5.0, 5.0 * ratio)
                pricing_scores.append(score)
            else:
                # No peer data - default to 5.0 so we don't penalize unique suppliers
                pricing_scores.append(5.0)
        
        self.auto_pricing_rating = sum(pricing_scores) / len(pricing_scores) if pricing_scores else 0.0
        
        self.save()


    @property
    def average_rating(self):
        avg = self.ratings.aggregate(avg_rating=Avg('rating'))['avg_rating']
        return float(avg) if avg else 0.0

    @property
    def full_stars(self):
        return int(self.average_rating)

    @property
    def empty_stars(self):
        has_half_star = (self.average_rating - self.full_stars) >= 0.5
        return 5 - self.full_stars - (1 if has_half_star else 0)

    def __str__(self):
        return f"{self.name} ({self.code})"

    

class Indent(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('po', 'Converted'),
        ('rejected', 'Rejected'), 
    ]


    title = models.CharField(max_length=255)
    indent_number = models.CharField(max_length=20, unique=True, blank=False, null=False)
    quantity = models.IntegerField(default=0)
    requested_by = models.CharField(max_length=100, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    reject_reason = models.TextField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_indents')
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="indents")
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="project_indents")
    required_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.indent_number} - {self.title}"


class IndentItem(models.Model):
    indent = models.ForeignKey(Indent, related_name="items", on_delete=models.CASCADE)
    product_name = models.CharField(max_length=255)
    product_code = models.CharField(max_length=50, blank=True, null=True)
    quantity = models.PositiveIntegerField()
    unit = models.CharField(max_length=50, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)
    shortage_qty = models.PositiveIntegerField(default=0)
    reject_reason = models.TextField(null=True, blank=True)
    SOURCE_CHOICES = [
    ('stock', 'Take From Stock'),
    ('purchase', 'Purchase'),
]
    source_type = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default='purchase',
        null=True, blank=True
    )
    approved = models.BooleanField(default=False)
    rejected = models.BooleanField(default=False)
    submitted = models.BooleanField(default=False)

    due_date = models.DateField(null=True, blank=True)
    vendor = models.ForeignKey(
        Vendor,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="indent_items"
    )
    production_item = models.ForeignKey(
        "InternalIndentItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="material_indents"
    )
    
    # Track how much has been issued to projects
    issued_qty = models.PositiveIntegerField(default=0)

    # Fulfillment Details
    stock_to_use = models.PositiveIntegerField(default=0)
    shortage_qty = models.PositiveIntegerField(default=0)  # PO Quantity
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.0)
    remarks = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.product_code:
            try:
                stock = StockItem.objects.get(product_name=self.product_name)
                self.product_code = stock.product_code
            except StockItem.DoesNotExist:
                # If product not in stock, generate a temporary code
                from django.utils.crypto import get_random_string
                prefix = self.product_name[:3].upper()
                self.product_code = f"{prefix}-{get_random_string(5).upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product_name} ({self.product_code}) - {self.quantity} {self.unit or ''}"




class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('received', 'Received'),
    ('partially_received', 'Partially Received'),
    # other statuses...
]
    indent = models.ForeignKey(Indent, on_delete=models.CASCADE, related_name="purchase_orders")
    po_number = models.CharField(max_length=100, unique=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    expected_delivery = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reject_reason = models.TextField(blank=True, null=True)
    delivery_delay_reason = models.TextField(blank=True, null=True)
    sent_to_vendor = models.BooleanField(default=False)
    proforma_invoice = models.FileField(upload_to="proforma_invoices/", null=True, blank=True)
    is_consolidated = models.BooleanField(default=False)
    last_bought_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    PAYMENT_TERM_CHOICES = [
        ('C&C', 'Cash & Carry'),
        ('Credit', 'Credit'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ]
    payment_terms = models.CharField(max_length=10, choices=PAYMENT_TERM_CHOICES, default='Credit')
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='unpaid')


    def __str__(self):
        return self.po_number

    def get_grand_total(self):
        return sum(item.total_price() for item in self.items.all())

    @property
    def due_date(self):
        """
        Returns the date when payment is due based on payment terms.
        C&C = Due immediately (created_at).
        Credit = Due after vendor's credit period.
        """
        if self.payment_terms == 'C&C':
            return self.created_at.date()
        
        days = self.vendor.credit_period_days or 0
        return (self.created_at + timedelta(days=days)).date()

class PurchaseOrderAttachment(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, related_name='attachments', on_delete=models.CASCADE)
    file = models.FileField(upload_to="proforma_invoices/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.purchase_order.po_number}"

class PurchaseItem(models.Model):
    po = models.ForeignKey(PurchaseOrder, related_name="items", on_delete=models.CASCADE)
    product_code = models.CharField(max_length=50)
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    remarks = models.TextField(blank=True, null=True)

    def total_price(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.product_name} ({self.quantity})"


import os, random
from io import BytesIO
from django.db import models
from django.conf import settings
from django.core.files.base import ContentFile
import qrcode
import barcode
from barcode.writer import ImageWriter
from barcode import Code128
from barcode import EAN13
from barcode.writer import ImageWriter

def generate_product_code():
    """Generate a random 13 digit code (like EAN-13) for internal use."""
    return str(random.randint(1000000000000, 9999999999999))


class StockItem(models.Model):
    STOCK_TYPES = [
        ("capital", "Capital Goods"),
        ("running", "Running Goods"),
        ("consumables", "Consumables"),
        ("finished", "Finished Goods"),
        ("semifinished", "Semi Finished Goods"),
        ("raw", "Raw Materials"),
    ]
    DEPARTMENTS = [
        ("RAF", "REACTOR ASSEMBLY FLOOR"),
        ("MSF", "MACHINE SHOP FLOOR "),
        ("PSF", "PLASTIC SHOP FLOOR "),
        ("WAH", "W&H"),
        ("ESD", "ELECTRONIC SYSTEM DESIGN"),
        ("PKG", "PACKING"),
        ("ALF", "ALF"),
    ]
    product_code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    product_name = models.CharField(max_length=255,unique=True)
    stock_type = models.CharField(max_length=20, choices=STOCK_TYPES, default="raw")
    department = models.CharField(max_length=20, choices=DEPARTMENTS, default="MSF")
    quantity = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)
    allocated = models.BooleanField(default=False)

    # Files
    barcode_image = models.ImageField(upload_to="barcodes/", blank=True, null=True)
    qr_code = models.ImageField(upload_to="barcodes/qrcodes/", blank=True, null=True)

    min_stock = models.PositiveIntegerField(default=0) # Minimum stock level alert

    def __str__(self):
        return f"{self.product_name} (Available: {self.quantity})"

    def save(self, *args, **kwargs):
        if not self.product_code or len(self.product_code) != 12:
            self.product_code = str(random.randint(10**11, 10**12 - 1))  

        super().save(*args, **kwargs)

        # --- Generate EAN13 Barcode ---
        filename = f"{self.product_code}_ean13.png"
        folder = os.path.join(settings.MEDIA_ROOT, "barcodes")
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, filename)

        ean = EAN13(self.product_code, writer=ImageWriter())
        ean.save(filepath.replace(".png", ""), {
            "module_height": 15,
            "font_size": 1,
            "quiet_zone": 2,
            "text_distance": 1
        })

        self.barcode_image = f"barcodes/{filename}"
        super().save(update_fields=["barcode_image"])

        # --- Generate QR Code ---
        local_url = f"http://{settings.ALLOWED_HOSTS[0]}:9004/product/{self.product_code}/"
        qr = qrcode.make(local_url)
        buffer = BytesIO()
        qr.save(buffer, format="PNG")
        qr_filename = f"{self.product_code}_qr.png"
        self.qr_code.save(qr_filename, ContentFile(buffer.getvalue()), save=False)
        super().save(update_fields=["qr_code"])


class VendorStock(models.Model):
    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name='vendor_mappings')
    vendor = models.ForeignKey('Vendor', on_delete=models.CASCADE, related_name='stock_supplies')
    price = models.DecimalField(max_digits=12, decimal_places=2, help_text="Unit Price")
    lead_time = models.PositiveIntegerField(help_text="Lead time in days", default=0)
    
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('stock_item', 'vendor')

    def __str__(self):
        return f"{self.stock_item.product_name} - {self.vendor} (₹{self.price})"


class StockLog(models.Model):
    TRANSACTION_TYPES = [
        ('ADD', 'Stock Addition'),
        ('SUBTRACT', 'Stock Reduction'),
        ('ISSUE', 'Material Issue'),
        ('GRN', 'GRN Receipt'),
        ('ADJUSTMENT', 'Manual Adjustment'),
        ('RETURN', 'Material Return'),
    ]

    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name='logs')
    change_quantity = models.IntegerField(help_text="Positive for addition, negative for deduction")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.stock_item.product_name}: {self.change_quantity} ({self.transaction_type})"


class MachineKit(models.Model):
    """
    Represents a standard Bill of Materials (BOM) or Kit for a specific machine capacity.
    Example: '6KLD STP Machine'
    """
    name = models.CharField(max_length=255, unique=True)
    product = models.ForeignKey(Products, on_delete=models.SET_NULL, null=True, blank=True, related_name='kits')
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class KitComponent(models.Model):
    """
    Represents a single item inside a MachineKit.
    """
    kit = models.ForeignKey(MachineKit, on_delete=models.CASCADE, related_name='components')
    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name='kit_components')
    parent_component = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_components')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='kit_components')
    category_name = models.CharField(max_length=100, blank=True, null=True, help_text="Category from Excel like 'IoT', 'TANKS', etc.")
    
    required_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1.0)
    uom = models.CharField(max_length=50, blank=True, null=True)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.stock_item.product_name} - {self.required_quantity} {self.uom} for {self.kit.name}"


from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class VendorRating(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name='ratings')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.DecimalField(
        max_digits=2, decimal_places=1,
        validators=[MinValueValidator(0.5), MaxValueValidator(5.0)]
    )  # Accepts 0.5 to 5.0
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.vendor.name} - {self.rating} stars by {self.user.username}"
    

class GRN(models.Model):

    GRN_TYPE_CHOICES = [
        ("purchase", "Purchase"),
        ("internal", "Internal"),
    ]

    # Purchase GRN
    po = models.ForeignKey(
        PurchaseOrder,
        related_name="grns",
        on_delete=models.CASCADE,
        null=True, blank=True
    )

    # Internal Indent GRN
    internal_indent = models.ForeignKey(
        "InternalIndent",
        related_name="internal_grns",
        on_delete=models.CASCADE,
        null=True, blank=True
    )

    grn_type = models.CharField(
        max_length=20,
        choices=GRN_TYPE_CHOICES,
        default="purchase"
    )

    grn_number = models.CharField(max_length=100, unique=True)
    received_date = models.DateField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    attachment = models.FileField(upload_to="grn_docs/", blank=True, null=True)

    def __str__(self):
        if self.grn_type == "purchase":
            return f"GRN {self.grn_number} for PO {self.po.po_number}"
        else:
            return f"IGRN {self.grn_number} for Internal Indent {self.internal_indent.indent_number}"

    def update_po_status(self):
        if self.grn_type != "purchase":
            return

        total_ordered = sum(item.quantity for item in self.po.items.all())
        total_received = sum(
            itm.accepted_qty
            for grn in self.po.grns.all()
            for itm in grn.items.all()
        )

        if total_received == 0:
            # Keep as approved if it was already approved
            if self.po.status != "approved":
                self.po.status = "approved"
        elif total_received < total_ordered:
            self.po.status = "partially_received"
        else:
            self.po.status = "received"

        self.po.save()


class GRNItem(models.Model):

    grn = models.ForeignKey(GRN, related_name="items", on_delete=models.CASCADE)

    # Purchase item (PO-based)
    purchase_item = models.ForeignKey(
        PurchaseItem,
        on_delete=models.CASCADE,
        null=True, blank=True
    )

    # Internal indent item (InternalIndentItem)
    internal_indent_item = models.ForeignKey(
        "InternalIndentItem",
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="internal_grn_items"
    )

    received_quantity = models.PositiveIntegerField()
    accepted_qty = models.PositiveIntegerField(default=0)
    rejected_qty = models.PositiveIntegerField(default=0)
    rejection_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        if self.purchase_item:
            name = self.purchase_item.product_name
        else:
            name = self.internal_indent_item.item_name
        return f"{name} - {self.received_quantity}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # 🟢 Internal GRN stock update
        if self.grn.grn_type == "internal":
            if self.internal_indent_item:
                stock_item, created = StockItem.objects.get_or_create(
                    product_name=self.internal_indent_item.item_name,
                    defaults={"quantity": 0, "stock_type": "semifinished"}
                )
                stock_item.quantity += self.accepted_qty
                stock_item.save()
                StockLog.objects.create(
                    stock_item=stock_item,
                    change_quantity=self.accepted_qty,
                    transaction_type='GRN',
                    description=f"Internal GRN Receipt: {self.grn.grn_number}",
                    user=self.grn.created_by
                )
            return

        # 🟢 Purchase GRN stock update
        stock_item = StockItem.objects.filter(
            product_code=self.purchase_item.product_code
        ).first()

        if stock_item:
            stock_item.quantity += self.accepted_qty
            stock_item.save()
            StockLog.objects.create(
                stock_item=stock_item,
                change_quantity=self.accepted_qty,
                transaction_type='GRN',
                description=f"GRN Receipt: {self.grn.grn_number}",
                user=self.grn.created_by
            )
        else:
            stock_item = StockItem.objects.filter(
                product_name=self.purchase_item.product_name
            ).first()

            if stock_item:
                stock_item.quantity += self.accepted_qty
                stock_item.save()
                StockLog.objects.create(
                    stock_item=stock_item,
                    change_quantity=self.accepted_qty,
                    transaction_type='GRN',
                    description=f"GRN Receipt: {self.grn.grn_number}",
                    user=self.grn.created_by
                )
            else:
                stock_item = StockItem.objects.create(
                    product_code=self.purchase_item.product_code,
                    product_name=self.purchase_item.product_name,
                    quantity=self.accepted_qty
                )
                StockLog.objects.create(
                    stock_item=stock_item,
                    change_quantity=self.accepted_qty,
                    transaction_type='GRN',
                    description=f"GRN Receipt: {self.grn.grn_number} (New Item)",
                    user=self.grn.created_by
                )

        self.grn.update_po_status()
        if self.grn.po and self.grn.po.vendor:
            self.grn.po.vendor.update_automated_ratings()
    



class BOM(models.Model):
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name="bom_items")
    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE)
    required_qty = models.PositiveIntegerField()
    issued_qty = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.stock_item.product_name} - {self.required_qty}"


class QCCheck(models.Model):
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name="qc_checks")
    checked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)
    passed = models.BooleanField(default=False)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"QC for {self.production_order} - {'Pass' if self.passed else 'Fail'}"


class TelemetryRecord(models.Model):
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name="telemetry_records")
    recorded_at = models.DateTimeField(auto_now_add=True)
    value = models.FloatField(null=True, blank=True)         # single reading
    timestamp = models.DateTimeField(null=True, blank=True)  # when reading taken
    remarks = models.TextField(blank=True, null=True)
    data = models.JSONField(blank=True, null=True)           # optional IoT bulk data


class Delivery(models.Model):
    production_order = models.OneToOneField(ProductionOrder, on_delete=models.CASCADE, related_name="delivery")
    prepared_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Delivery for {self.production_order}"
    

class ProductBOM(models.Model):
    product = models.ForeignKey(Products, on_delete=models.CASCADE, related_name="bom_template")
    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.product.name} requires {self.quantity} x {self.stock_item.product_name}"
    
class MaterialIssue(models.Model):
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name="issues", null=True, blank=True)
    project = models.ForeignKey("Project", on_delete=models.CASCADE, related_name="material_issues", null=True, blank=True)
    stock_item = models.ForeignKey(StockItem, on_delete=models.CASCADE)
    issued_qty = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Price per unit")
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    internal_indent_item = models.ForeignKey(
        "InternalIndentItem",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="direct_issues"
    )

    def clean(self):
        from django.core.exceptions import ValidationError
        # Only validate if this is an existing instance being updated
        # Skip validation during form creation (when pk is None)
        if self.pk and not self.production_order and not self.project:
            raise ValidationError("Either Production Order or Project must be selected.")
    
    def total_value(self):
        """Calculate total value of this issue"""
        return self.issued_qty * self.unit_price

    def __str__(self):
        target = self.production_order if self.production_order else self.project
        return f"Issued {self.issued_qty} {self.stock_item.product_name} to {target}"
    



class ProductionOrderItem(models.Model):
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name="items")
    product_code = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True, null=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    uom = models.CharField(max_length=20, default="Nos")

    def __str__(self):
        return f"{self.product_code} ({self.quantity} {self.uom})"


class IndentRequest(models.Model):
    production_order = models.ForeignKey(ProductionOrder, on_delete=models.CASCADE, related_name="indent_requests")
    indent = models.OneToOneField(Indent, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Indent for {self.production_order.order_number}"
    
    
from django.db import models
from django.conf import settings

class Snag(models.Model):
    SNAP_TYPE_CHOICES = [
        ("material", "Material Shortage"),
        ("assembly", "Assembly Line Disruption"),
        ("vendor", "Vendor Delay"),
        ("quality", "Quality Failure"),
        ("approval", "Approval or Documentation Delay"),
        ("other", "Other"),
    ]

    production_order = models.ForeignKey("ProductionOrder", on_delete=models.CASCADE)
    production_item = models.ForeignKey("ProductionOrderItem", on_delete=models.CASCADE, null=True, blank=True)
    snap_type = models.CharField(max_length=50, choices=SNAP_TYPE_CHOICES)
    description = models.TextField(blank=True, null=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    reported_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.get_snap_type_display()} - {self.production_order}"
    


# models.py (add these classes to your indent app's models.py)
from django.db import models
from django.conf import settings

class InternalIndent(models.Model):
    project = models.ForeignKey("Project", on_delete=models.CASCADE)
    department = models.ForeignKey("Department", on_delete=models.CASCADE)
    indent_number = models.CharField(max_length=30, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, default="internal")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("project", "department")  # only one active internal indent per project+dept

    def __str__(self):
        return f"{self.indent_number} — {self.project} / {self.department}"


class InternalIndentItem(models.Model):
    internal_indent = models.ForeignKey(InternalIndent, related_name="items", on_delete=models.CASCADE)
    item_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    due_date = models.DateField(null=True, blank=True)
    requested_by_dept = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True, blank=True, related_name="requested_items")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.item_name} x {self.quantity}"
    


    


    
class EmailLog(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="email_logs")
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    attachment = models.FileField(upload_to="email_logs/", null=True, blank=True)

    def __str__(self):
        return f"Email to {self.recipient} regarding {self.purchase_order}"


class WhatsAppLog(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="whatsapp_logs")
    recipient_number = models.CharField(max_length=20)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"WhatsApp to {self.recipient_number} about {self.purchase_order}"


class Deployment(models.Model):
    STATUS_CHOICES = [
        ("loading", "Loading"),
        ("dispatched", "Dispatched"),
        ("delivered", "Delivered"),
    ]

    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="deployment")
    
    # Snapshot of SFG progress at the moment of pushing to deployment
    department_status_snapshot = models.JSONField(blank=True, null=True)

    deployed_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="loading")

    def __str__(self):
        return f"Deployment for {self.project.name}"

class DeploymentImage(models.Model):
    IMAGE_TYPE_CHOICES = [
        ('loading', 'Loading'),
        ('unloading', 'Unloading'),
    ]
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="deployment_images/")
    image_type = models.CharField(max_length=20, choices=IMAGE_TYPE_CHOICES, default='loading')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.deployment.project.name}"

class DeploymentDocument(models.Model):
    DOCUMENT_TYPES = [
        ('lr_copy', 'LR Copy'),
        ('e_sugam', 'E-SUGAM'),
        ('invoice', 'Invoice'),
        ('user_manual', 'User Manual'),
        ('insurance_copy', 'Insurance Copy'),
        # Generated documents
        ('warranty', 'Warranty Certificate'),
        ('guarantee', 'Guarantee Certificate'),
        ('dc', 'Delivery Challan'),
        ('commissioning', 'Commissioning Report'),
        ('handover', 'Handover Document'),
    ]
    deployment = models.ForeignKey(Deployment, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to="deployment_docs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_document_type_display()} for {self.deployment.project.name}"

class POPaymentLog(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="payment_logs")
    purchase_orders = models.ManyToManyField(PurchaseOrder, related_name="payment_logs")
    transaction_id = models.CharField(max_length=100)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2)
    payment_proof = models.FileField(upload_to="payment_proofs/", null=True, blank=True)
    remarks = models.TextField(blank=True, null=True)
    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.transaction_id} for {self.vendor.name}"

