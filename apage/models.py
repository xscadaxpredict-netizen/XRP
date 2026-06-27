from django.db import models
from datetime import datetime, timedelta
from django.utils.timezone import now
import json
from django.contrib.auth.models import User
from django.utils import timezone
from app.models import Zone


from django.core.exceptions import ValidationError
from datetime import date ,timedelta


def no_future_dates(value):
    print(f"Validating date: {value}")
    if value > date.today() + timedelta(days=1):  # Allows today, restricts tomorrow onward
        raise ValidationError("Future dates are not allowed.")


class Site(models.Model):
    name = models.CharField(max_length=100)
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE , null=True, blank=True)

    def __str__(self):
        return self.name

class GeneralReport(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True)
    date_of_visit = models.DateField(validators=[no_future_dates])
    point1 = models.TextField()
    point2 = models.TextField()
    point3 = models.TextField()
    point4 = models.TextField()
    notes = models.TextField()
    attachment = models.FileField(upload_to='attachments/', null=True, blank=True)
    edit_history = models.TextField(blank=True, null=True)  # To store edit history
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_date = models.DateField(default=timezone.now)
    
    def update_history(self, field_name, old_value, new_value):
        from datetime import datetime, timedelta
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        history_entry = f"- {field_name} changed from '{old_value}' to '{new_value}' on {timestamp}\n"
        
        if self.edit_history:
            self.edit_history += history_entry  # Append new entry
        else:
            self.edit_history = history_entry

    def save(self, *args, **kwargs):
        # We add a flag to prevent recursion when saving the object
        if not hasattr(self, '_updating_history'):  # Check if the flag is set
            self._updating_history = True  # Set the flag to True

            if self.pk:  # If it's not a new object, track changes
                original = GeneralReport.objects.get(pk=self.pk)
                
                # Track changes in each field
                if self.site != original.site:
                    self.update_history("Site", original.site.name, self.site.name)
                if self.point1 != original.point1:
                    self.update_history("Point 1", original.point1, self.point1)
                if self.point2 != original.point2:
                    self.update_history("Point 2", original.point2, self.point2)
                if self.point3 != original.point3:
                    self.update_history("Point 3", original.point3, self.point3)
                if self.point4 != original.point4:
                    self.update_history("Point 4", original.point4, self.point4)
                if self.notes != original.notes:
                    self.update_history("Notes", original.notes, self.notes)
                if self.date_of_visit != original.date_of_visit:
                    self.update_history("Date of Visit", original.date_of_visit, self.date_of_visit)
                if self.attachment != original.attachment:
                    old_attachment = original.attachment.url if original.attachment else "No Attachment"
                    new_attachment = self.attachment.url if self.attachment else "No Attachment"
                    self.update_history("Attachment", old_attachment, new_attachment)

            super().save(*args, **kwargs)  # Now it will save without recursion
            del self._updating_history  # Remove the flag after saving
        else:
            # If the flag is set, skip saving to prevent recursion
            super().save(*args, **kwargs)


    def __str__(self):
        return f"Report for {self.site.name} on {self.date_of_visit}"




# -----------------------------MaintenanceChecklist-----------------------------------
class Machine(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class MaintenanceChecklist(models.Model):
    inspector_name = models.CharField(max_length=255, null=True, blank=True)  # Auto-filled by logged-in user
    date = models.DateField()  # Stores the current date
    machine = models.ForeignKey(Machine, on_delete=models.CASCADE)
    visit_date = models.DateField(validators=[no_future_dates])
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True)
    # Supply Voltage choices (useful for retrieving and editing)
    SUPPLY_VOLTAGE_CHOICES = [
        ('checked', 'Checked'),
        ('repair', 'Repair'),
        ('replacement', 'Replacement'),
    ]
    supply_voltage = models.CharField(
        max_length=20, choices=SUPPLY_VOLTAGE_CHOICES, blank=True, null=True
    )
    
    # Current Load choices (useful for retrieving and editing)
    CURRENT_LOAD_CHOICES = [
        ('checked', 'Checked'),
        ('repair', 'Repair'),
        ('replacement', 'Replacement'),
    ]
    current_load = models.CharField(
        max_length=20, choices=CURRENT_LOAD_CHOICES, blank=True, null=True
    )
    
    # Observations (useful for retrieving and editing)
    observations = models.TextField(blank=True, null=True)
    # Edit history field to track changes
    edit_history = models.TextField(blank=True, null=True)  # To store edit history

    def update_history(self, field_name, old_value, new_value):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        history_entry = f"- {field_name} changed from '{old_value}' to '{new_value}' on {timestamp}\n"
        
        if self.edit_history:
            self.edit_history += history_entry  # Append new entry
        else:
            self.edit_history = history_entry
    
    def save(self, *args, **kwargs):
        if self.pk:  # If it's not a new object, track changes
            original = MaintenanceChecklist.objects.get(pk=self.pk)

            # Track changes in fields
            if self.machine != original.machine:
                self.update_history("Machine", original.machine.name, self.machine.name)
            if self.visit_date != original.visit_date:
                self.update_history("Visit Date", original.visit_date, self.visit_date)
            if self.supply_voltage != original.supply_voltage:
                self.update_history("Supply Voltage", original.supply_voltage, self.supply_voltage)
            if self.current_load != original.current_load:
                self.update_history("Current Load", original.current_load, self.current_load)
            if self.observations != original.observations:
                self.update_history("Observations", original.observations, self.observations)

            # Track changes to attachments
            original_attachments = set(original.attachments.all())
            current_attachments = set(self.attachments.all())

            added_attachments = current_attachments - original_attachments
            removed_attachments = original_attachments - current_attachments

            for attachment in added_attachments:
                self.update_history("Attachment Added", "None", attachment.file.name)

            for attachment in removed_attachments:
                self.update_history("Attachment Removed", attachment.file.name, "None")

        super().save(*args, **kwargs)


    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending'
    )

    def approve(self):
        self.status = 'approved'
        self.save()

    def reject(self):
        self.status = 'rejected'
        self.save()

    def __str__(self):
        return f"{self.machine.name} - {self.visit_date} ({self.get_status_display()})"
    
class MaintenanceChecklistAttachment(models.Model):
    checklist = models.ForeignKey(MaintenanceChecklist, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='attachments/')
    edit_history = models.TextField(blank=True, null=True)  # Edit history for file changes

    def update_history(self, field_name, old_value, new_value):
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        history_entry = f"- {field_name} changed from '{old_value}' to '{new_value}' on {timestamp}\n"
        
        if self.edit_history:
            self.edit_history += history_entry  # Append new entry
        else:
            self.edit_history = history_entry

    def save(self, *args, **kwargs):
        if self.pk:  # If it's not a new object, track changes
            original = MaintenanceChecklistAttachment.objects.get(pk=self.pk)
            if self.file != original.file:
                self.update_history("File", original.file.name if original.file else 'None', self.file.name)
        
        super().save(*args, **kwargs)

    
# ----------------------------------------mom---------------------------------
from django.db import models

class MOM(models.Model):
    topic = models.CharField(max_length=255)
    organize = models.CharField(max_length=255)
    meeting_chair = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    date = models.DateField(validators=[no_future_dates])
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration = models.CharField(max_length=255, blank=True)
    updated_by = models.CharField(max_length=255)
    meeting_conclusion = models.TextField()
    summary_of_discussion = models.TextField()
    attendees = models.JSONField(default=list)
    apologies = models.JSONField(default=list)
    agenda = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    edit_history = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True)
    created_date = models.DateField(default=timezone.now)

    def update_history(self, field_name, old_value, new_value, editor): 
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        history_entry = f"[{timestamp}] {field_name} changed by {editor} from '{old_value}' to '{new_value}'\n"

        if self.edit_history:
            self.edit_history += history_entry
        else:
            self.edit_history = history_entry

    def save(self, *args, **kwargs):
        if self.pk:  # If this is an update
            original = MOM.objects.get(pk=self.pk)

            # Track changes for relevant fields
            fields_to_check = [
                'topic', 'organize', 'meeting_chair', 'location',
                'date', 'start_time', 'end_time', 'duration',
                'meeting_conclusion', 'summary_of_discussion',
                'attendees', 'apologies', 'agenda'
            ]
            for field in fields_to_check:
                old_value = getattr(original, field)
                new_value = getattr(self, field)
                if old_value != new_value:
                    self.update_history(
                        field_name=field.replace('_', ' ').capitalize(),
                        old_value=json.dumps(old_value, default=str) if isinstance(old_value, list) else old_value,
                        new_value=json.dumps(new_value, default=str) if isinstance(new_value, list) else new_value,
                        editor=self.updated_by
                    )

        super().save(*args, **kwargs)

    def __str__(self):
        return self.topic

class Attachment(models.Model):
    file = models.FileField(upload_to='meetings/attachments/')
    meeting = models.ForeignKey(MOM, related_name='attachments', on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name


# --------------------------------service report ----------------------


from django.db import models

class ElectronicItem(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name
    
class ElectronicPanel(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name
class ChemicalItem(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name
    
class Pump(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name
    
class MiscellaneousItem(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

class WastewaterParameter(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name
# --------------------------------------------------------------------------

class State(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name
    


class ServiceReport(models.Model):
    service_name = models.CharField(max_length=255)
    date_of_visit = models.DateField(validators=[no_future_dates], null=True, blank=True)
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='service_reports')
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True, blank=True, related_name='service_reports')
    phone_no = models.CharField(max_length=15, null=True, blank=True)    
    reason_of_visit = models.CharField(max_length=255, null=True, blank=True)
    in_time = models.TimeField(null=True, blank=True)
    out_time = models.TimeField(null=True, blank=True)
    other_remarks = models.TextField(blank=True, null=True, help_text="Store all other remarks concatenated.")
    spares_details = models.TextField(blank=True, null=True, help_text="Concatenated spares details")
    service_person_signature = models.TextField(blank=True, null=True, help_text="Base64-encoded signature of the service person.")
    service_person_name = models.CharField(max_length=255, blank=True, null=True, help_text="Name of the service person.")
    client_signature = models.TextField(blank=True, null=True, help_text="Base64-encoded signature of the client.")
    client_name = models.CharField(max_length=255, blank=True, null=True, help_text="Name of the client.")
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True)
    created_date = models.DateField(default=timezone.now)
    # Customer Information
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    contact_number = models.CharField(max_length=15, null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True)
    date_of_complaint = models.DateField(null=True, blank=True)
    status_of_call = models.CharField(max_length=100, null=True, blank=True)

    
    electronic_items = models.ManyToManyField(ElectronicItem, through='ElectronicItemStatus')
    electronic_panels = models.ManyToManyField(ElectronicPanel, through='ElectronicPanelStatus')
    chemical_items = models.ManyToManyField(ChemicalItem, through='ChemicalItemStatus')
    pumps = models.ManyToManyField(Pump, through='PumpStatus')
    miscellaneous_items = models.ManyToManyField(MiscellaneousItem, through='MiscellaneousItemStatus')
    wastewater_parameters = models.ManyToManyField(WastewaterParameter, through='WastewaterParameterStatus')
    client_signed = models.BooleanField(default=False)  # ✅ NEW
    client_remark = models.TextField(blank=True, null=True, help_text="Remarks given by the client while signing.")
    is_draft = models.BooleanField(default=False)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    rejection_reason = models.TextField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
    )

    def approve(self):
        self.status = 'approved'
        self.rejection_reason = None  # Clear if previously rejected
        self.save()

    def reject(self, reason=None):
        self.status = 'rejected'
        self.rejection_reason = reason
        self.save()

    def __str__(self):
        return f"Service Report for {self.service_name} - {self.customer_name} ({self.get_status_display()})"

    class Meta:
        verbose_name = 'Service Report'
        verbose_name_plural = 'Service Reports'

# models.py

from django.db import models
from datetime import timedelta
from django.utils import timezone
from .models import Site  # Adjust import as per your structure

class SiteVisitSchedule(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='visit_schedules', unique=True)
    last_visit = models.DateField()
    next_due = models.DateField()

    def __str__(self):
        return f"{self.site.name} - Last: {self.last_visit}, Next Due: {self.next_due}"

class ServiceReportAttachment(models.Model):
    service_report = models.ForeignKey(
        ServiceReport,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to="service_reports/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.service_report.service_name} - {self.file.name}"

class ElectronicItemStatus(models.Model):
    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE)
    item = models.ForeignKey(ElectronicItem, on_delete=models.CASCADE)
    checked = models.BooleanField(default=False)
    repair = models.BooleanField(default=False)
    replacement = models.BooleanField(default=False)
    remark = models.TextField(blank=True, null=True)

class ElectronicPanelStatus(models.Model):
    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE)
    panel = models.ForeignKey(ElectronicPanel, on_delete=models.CASCADE)
    checked = models.BooleanField(default=False)
    repair = models.BooleanField(default=False)
    replacement = models.BooleanField(default=False)
    remark = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.report} - {self.panel.name}"

class ChemicalItemStatus(models.Model):
    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE)
    item = models.ForeignKey(ChemicalItem, on_delete=models.CASCADE)
    checked = models.BooleanField(default=False)
    repair = models.BooleanField(default=False)
    replacement = models.BooleanField(default=False)
    remark = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.report} - {self.item.name}"
class PumpStatus(models.Model):
    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE)
    pump = models.ForeignKey(Pump, on_delete=models.CASCADE)
    checked = models.BooleanField(default=False)
    repair = models.BooleanField(default=False)
    replacement = models.BooleanField(default=False)
    remark = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.report} - {self.pump.name}"

class MiscellaneousItemStatus(models.Model):
    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE)
    item = models.ForeignKey(MiscellaneousItem, on_delete=models.CASCADE)
    checked = models.BooleanField(default=False)
    repair = models.BooleanField(default=False)
    replacement = models.BooleanField(default=False)
    remark = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.report} - {self.item.name}"

class WastewaterParameterStatus(models.Model):
    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE)
    parameter = models.ForeignKey(WastewaterParameter, on_delete=models.CASCADE)
    checked = models.BooleanField(default=False)
    repair = models.BooleanField(default=False)
    replacement = models.BooleanField(default=False)
    remark = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.report} - {self.parameter.name}"
    
class MachineRunTime(models.Model):
    service_report = models.ForeignKey(ServiceReport, related_name='run_times', on_delete=models.CASCADE)
    run_type = models.CharField(max_length=255)  # Example: Run cycle 1, Run cycle 2, etc.
    run_time = models.TimeField()
    end_time = models.TimeField()
    checked = models.BooleanField(default=False)
    pass_status = models.BooleanField(default=False)
    fail_status = models.BooleanField(default=False)
    remark = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.run_type} - {self.run_time} to {self.end_time}'
    

class Tool(models.Model):
    name = models.CharField(max_length=100)
    details = models.CharField(max_length=255, blank=True, null=True ,default='')

    def __str__(self):
        return self.name

class ToolStatus(models.Model):
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    service_report = models.ForeignKey('ServiceReport', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, null=False, blank=False)
    remark = models.TextField(blank=True, null=True)
    taken_status = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.tool.name} - {self.service_report.id}"




class ServiceReportEditLog(models.Model):
    report = models.ForeignKey(ServiceReport, on_delete=models.CASCADE)
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    edit_timestamp = models.DateTimeField(auto_now_add=True)
    field_changed = models.CharField(max_length=255)
    old_value = models.TextField()
    new_value = models.TextField()

    def __str__(self):
        return f"Edit log for {self.report} on {self.edit_timestamp}"

# ---------------------------------------------Generator Report ----------------------------------------------

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class GeneratorReport(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    total_time = models.DurationField(null=True, blank=True)

    def clean(self):
        """
        Ensures that a new entry cannot be created if the last entry is missing an 'end_time'.
        Also validates that end_time is always after start_time, allowing next-day shifts.
        """
        last_entry = GeneratorReport.objects.filter(created_by=self.created_by).order_by('-id').first()

        if last_entry and last_entry.end_time is None and self.pk is None:
            raise ValidationError("Cannot create a new entry while the last entry has an empty 'end_time'.")

        # Validate time sequence
        if self.start_time and self.end_time:
            start_datetime = datetime.combine(self.date, self.start_time)
            end_datetime = datetime.combine(self.date, self.end_time)

            # ✅ Handle overnight shift (next-day)
            if self.end_time < self.start_time:
                end_datetime += timedelta(days=1)

            duration_minutes = (end_datetime - start_datetime).total_seconds() / 60

            # ✅ Ensure duration is valid (between 1 minute and 24 hours max)
            if duration_minutes <= 0 or duration_minutes > 1440:
                raise ValidationError("⚠️ Invalid End Time: Must be after Start Time and within 24 hours!")

    def save(self, *args, **kwargs):
        """
        Auto-compute total_time when end_time is provided, supporting next-day shifts.
        """
        self.full_clean()  # Run validation before saving

        if self.start_time and self.end_time:
            start_datetime = datetime.combine(self.date, self.start_time)
            end_datetime = datetime.combine(self.date, self.end_time)

            if self.end_time < self.start_time:  # ✅ Handle next-day shifts
                end_datetime += timedelta(days=1)

            self.total_time = end_datetime - start_datetime
        else:
            self.total_time = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Generator Report - {self.date} ({self.start_time} - {self.end_time or 'Ongoing'})"


class SiteAMC(models.Model):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, related_name='amc_details')
    has_amc = models.BooleanField(default=False)
    amc_start_date = models.DateField(null=True, blank=True)
    amc_end_date = models.DateField(null=True, blank=True)
    proof_file = models.FileField(upload_to='amc_proofs/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"AMC for {self.site.name}"

class Bike(models.Model):
    registration_number = models.CharField(max_length=50, unique=True)
    model_name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.registration_number} - {self.model_name}"

class BikeMaintenance(models.Model):
    bike = models.ForeignKey(Bike, on_delete=models.CASCADE, related_name='maintenances')
    date = models.DateField(auto_now_add=True)
    oil_change_date = models.DateField(null=True, blank=True)
    current_mileage = models.IntegerField(help_text="Current odometer reading")
    
    # Previous Service Data
    last_oil_change_or_service_date = models.DateField(null=True, blank=True)
    last_oil_change_km = models.IntegerField(null=True, blank=True)
    
    # Routine Checks
    brakes_ok = models.BooleanField(default=True)
    tires_ok = models.BooleanField(default=True)
    lights_ok = models.BooleanField(default=True)
    
    issues_faced = models.TextField(blank=True, null=True)
    tagged_users = models.ManyToManyField(User, blank=True, related_name='tagged_bike_issues')
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reported_bike_issues')

    def __str__(self):
        return f"Maintenance for {self.bike.registration_number} on {self.date}"

class BikeMaintenancePhoto(models.Model):
    maintenance = models.ForeignKey(BikeMaintenance, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='bike_maintenance_photos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo for {self.maintenance}"


class Service(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ServiceExpiry(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='expiries')
    expiry_date = models.DateField()
    email = models.EmailField(help_text="Email of the respective person to notify")
    notified = models.BooleanField(default=False)
    last_notified_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.service.name} expiring on {self.expiry_date} (Notify: {self.email})"
