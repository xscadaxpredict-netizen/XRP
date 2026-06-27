from django.contrib import admin
from .models import GeneralReport , GeneratorReport,SiteVisitSchedule,BikeMaintenance,Bike

admin.site.register(GeneralReport)
admin.site.register(SiteVisitSchedule)
admin.site.register(BikeMaintenance)
admin.site.register(Bike)

# -------------------MaintenanceChecklist------------------

from django.contrib import admin
from .models import Machine, MaintenanceChecklist ,MaintenanceChecklistAttachment

@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(MaintenanceChecklist)
class MaintenanceChecklistAdmin(admin.ModelAdmin):
    list_display = ('inspector_name', 'machine', 'visit_date','edit_history')
    list_filter = ('date', 'machine')

@admin.register(MaintenanceChecklistAttachment)
class MaintenanceChecklistAttachmentAdmin(admin.ModelAdmin):
    list_display = ('checklist', 'file' ,'edit_history')
    search_fields = ('checklist__inspector_name', 'file')




# ---------------------GeneralReport----------------------
from django.contrib import admin
from .models import Site

# Register the Site model with the admin interface
@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('name', 'zone')
    search_fields = ('name', 'zone__name')

# -------------------------------MOM------------------------
from django.contrib import admin
from .models import MOM, Attachment

class MOMAdmin(admin.ModelAdmin):
    list_display = ('topic', 'organize', 'meeting_chair', 'date', 'updated_at')
    search_fields = ('topic', 'organize', 'meeting_chair')
    list_filter = ('date', 'location')

class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('file', 'meeting', 'uploaded_at')
    search_fields = ('file', 'meeting__topic')

admin.site.register(MOM, MOMAdmin)
admin.site.register(Attachment, AttachmentAdmin)


# -------------------------------ServiceReport------------------------


from django.contrib import admin
from .models import ElectronicItem, ServiceReport, ElectronicItemStatus ,ElectronicPanel,ElectronicPanelStatus ,ChemicalItem ,ChemicalItemStatus
from .models import Pump, PumpStatus ,MiscellaneousItem ,MiscellaneousItemStatus ,WastewaterParameter, WastewaterParameterStatus ,MachineRunTime
from .models import ToolStatus,Tool , State
# Register ElectronicItem
@admin.register(ElectronicItem)
class ElectronicItemAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

# Register ServiceReport
@admin.register(ServiceReport)
class ServiceReportAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'customer_name', 'date_of_visit')
    list_filter = ( 'date_of_visit', 'status_of_call')
    search_fields = ('service_name', 'customer_name', 'phone_no', 'location')

# Register ElectronicItemStatus
@admin.register(ElectronicItemStatus)
class ElectronicItemStatusAdmin(admin.ModelAdmin):
    list_display = ('report', 'item', 'checked', 'repair', 'replacement', 'remark')
    list_filter = ('checked', 'repair', 'replacement')
    search_fields = ('report__service_name', 'item__name', 'remark')

# Register ElectronicItem
@admin.register(ElectronicPanel)
class ElectronicItemAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
@admin.register(ElectronicPanelStatus)
class ElectronicPanelStatus(admin.ModelAdmin):
    list_display = ('report', 'panel', 'checked', 'repair', 'replacement', 'remark')
    list_filter = ('checked', 'repair', 'replacement')
    search_fields = ('report__service_name', 'panel__name', 'remark')
# Chemical Item
@admin.register(ChemicalItem)
class ChemicalItemAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(ChemicalItemStatus)
class ChemicalItemStatusAdmin(admin.ModelAdmin):
    list_display = ('report', 'item', 'checked', 'repair', 'replacement', 'remark')
    list_filter = ('checked', 'repair', 'replacement')
    search_fields = ('report__service_name', 'item__name', 'remark')
# pumps
@admin.register(Pump)
class PumpAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(PumpStatus)
class PumpStatusAdmin(admin.ModelAdmin):
    list_display = ('report', 'pump', 'checked', 'repair', 'replacement', 'remark')
    list_filter = ('checked', 'repair', 'replacement')
    search_fields = ('report__service_name', 'pump__name', 'remark')
# MiscellaneousItem
@admin.register(MiscellaneousItem)
class MiscellaneousItemAdmin(admin.ModelAdmin):
    list_display = ('name',)  # Displays the name in the list view
    search_fields = ('name',)  # Allows searching by name

@admin.register(MiscellaneousItemStatus)
class MiscellaneousItemStatusAdmin(admin.ModelAdmin):
    list_display = ('report', 'item', 'checked', 'repair', 'replacement', 'remark')
    list_filter = ('checked', 'repair', 'replacement')  # Filters for checked, repair, replacement fields
    search_fields = ('report__service_name', 'item__name', 'remark')  # Enables search by report service name, item name, and remarks

# WastewaterParameter
@admin.register(WastewaterParameter)
class WastewaterParameterAdmin(admin.ModelAdmin):
    list_display = ('name',)  # Displays the name in the list view
    search_fields = ('name',)  # Allows searching by name

@admin.register(WastewaterParameterStatus)
class WastewaterParameterStatusAdmin(admin.ModelAdmin):
    list_display = ('report', 'parameter', 'checked', 'repair', 'replacement', 'remark')
    list_filter = ('checked', 'repair', 'replacement')  # Filters for checked, repair, replacement fields
    search_fields = ('report__service_name', 'parameter__name', 'remark')  # Enables search by report service name, parameter name, and remarks
# MachineRunTime
@admin.register(MachineRunTime)
class MachineRunTimeAdmin(admin.ModelAdmin):
    list_display = ('run_type', 'run_time', 'end_time', 'checked', 'pass_status', 'fail_status', 'remark')
    list_filter = ('checked', 'pass_status', 'fail_status')
    search_fields = ('run_type', 'remark', 'service_report__service_name')

# toolkits

@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ('name', 'details')  # Fields to display in the list view
    search_fields = ('name',)  # Fields to search in the admin interface

# Register the ToolStatus model
@admin.register(ToolStatus)
class ToolStatusAdmin(admin.ModelAdmin):
    list_display = ('tool', 'service_report', 'quantity', 'remark', 'taken_status')  # Fields to display
    list_filter = ('tool', 'service_report', 'taken_status')  # Filter options
    search_fields = ('tool__name', 'service_report__id')  # Fields to search


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

from .models import ServiceReportEditLog

@admin.register(ServiceReportEditLog)
class ServiceReportEditLogAdmin(admin.ModelAdmin):
    list_display = ('report', 'edited_by', 'edit_timestamp', 'field_changed', 'old_value', 'new_value')
    list_filter = ('edit_timestamp', 'field_changed', 'edited_by')
    search_fields = ('report__id', 'field_changed', 'old_value', 'new_value')
    ordering = ('-edit_timestamp',)

# ---------------------GeneratorReport----------------------



from datetime import datetime, timedelta
@admin.register(GeneratorReport)
class GeneratorReportAdmin(admin.ModelAdmin):
    list_display = ('created_by', 'date', 'start_time', 'end_time', 'get_total_time')
    search_fields = ('created_by__username', 'date')
    list_filter = ('date',)

    def get_total_time(self, obj):
        if obj.start_time and obj.end_time:
            start_time = datetime.combine(obj.date, obj.start_time)
            end_time = datetime.combine(obj.date, obj.end_time)

            # If end_time is before start_time but within a reasonable time window (e.g., next-day case)
            if end_time < start_time:
                # Only allow a next-day adjustment if the difference is within a reasonable range
                if (start_time - end_time).seconds <= 12 * 3600:  # Max 12-hour shift assumption
                    end_time += timedelta(days=1)
                else:
                    return "Invalid Time"  # Block cases like 8 PM → 7 PM

            total_time = end_time - start_time
            hours, remainder = divmod(total_time.total_seconds(), 3600)
            minutes = remainder // 60

            return f"{int(hours)}h {int(minutes)}m"

        return "N/A"

    get_total_time.short_description = "Total Time"


from .models import Service, ServiceExpiry

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(ServiceExpiry)
class ServiceExpiryAdmin(admin.ModelAdmin):
    list_display = ('service', 'expiry_date', 'email', 'notified', 'created_at')
    list_filter = ('expiry_date', 'notified')
    search_fields = ('service__name', 'email')


