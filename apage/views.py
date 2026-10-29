from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from xhtml2pdf import pisa
from django.shortcuts import render, redirect ,get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, authentication_classes, permission_classes, parser_classes
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser



from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from django.http import HttpResponse

from app.models import ModuleVisibility
import os

def link_callback(uri, rel):
    """
    Convert HTML images/links to local system paths for xhtml2pdf.
    """
    from django.conf import settings
    
    # Handle media files
    if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, "", 1))
    # Handle static files
    elif settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, "", 1))
        # If static files aren't collected, search in static dirs
        if not os.path.exists(path) and hasattr(settings, 'STATICFILES_DIRS'):
            for static_dir in settings.STATICFILES_DIRS:
                potential_path = os.path.join(static_dir, uri.replace(settings.STATIC_URL, "", 1))
                if os.path.exists(potential_path):
                    path = potential_path
                    break
    else:
        # If the URI is already a local file path starting with file://
        if uri.startswith('file://'):
            path = uri.replace('file://', '', 1)
        else:
            return uri

    # Make sure that file exists
    if not os.path.exists(path):
        return uri
    return path


def base(request):
    return render(request ,'base.html')

def home(request):
    return render(request, 'apage/home.html')
def homea(request):
    return render(request, 'base_generic.html')
def  success(request):
    return render(request,'apage/success')
# -----------------------------MaintenanceChecklist-----------------------------------

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import MaintenanceChecklist, Machine ,MaintenanceChecklistAttachment
from datetime import date


@login_required
def update_status(request, pk, action):
    checklist = get_object_or_404(MaintenanceChecklist, pk=pk)
    
    # if not request.user.is_staff:  # Restrict to admin users
    #     return HttpResponseForbidden("You do not have permission to perform this action.")

    if action == 'approve':
        checklist.approve()
    elif action == 'reject':
        checklist.reject()
    else:
        return HttpResponseForbidden("Invalid action.")
    
    return redirect('maintenance_checklist')  # Redirect to the checklist list page or any relevant page

def maintenance_checklist_detail(request, checklist_id):
    checklist = get_object_or_404(MaintenanceChecklist, id=checklist_id)
    attachments = checklist.attachments.all()  # Access all related attachments

    return render(request, 'apage/edithistory_maintenance.html', {
        'checklist': checklist,
        'attachments':attachments,
    })

@login_required
def maintenance_checklist_records(request):
    machines = Machine.objects.all()

    if request.method == 'POST':
        machine_id = request.POST.get('machine_name')
        visit_date = request.POST.get('visit_date')
        supply_voltage = request.POST.get('supply_voltage')
        supply_voltage_details = request.POST.get('supply_voltage_details', '')
        current_load = request.POST.get('current_load')
        current_load_details = request.POST.get('current_load_details', '')
        observations = request.POST.getlist('observation[]')  # List of observations
        attachments = request.FILES.getlist('attachment[]')  # Get multiple attachments

        # Validate required fields
        if not supply_voltage:
            return HttpResponse("Please select a supply voltage.", status=400)

        if not current_load:
            return HttpResponse("Please select a current load.", status=400)

        # Capture the current date when the form is submitted
        current_date = date.today()

        try:
            machine = Machine.objects.get(id=machine_id)
        except Machine.DoesNotExist:
            return HttpResponse("Machine not found.", status=404)

        # Concatenate observations into a single string if needed
        observations_text = "\n".join(observations)

        # Create the Maintenance Checklist entry with individual fields
        checklist = MaintenanceChecklist(
            inspector_name=request.user.username,  # Auto-fill with logged-in user's username
            machine=machine,
            visit_date=visit_date,
            supply_voltage=supply_voltage,  # Store directly in the supply_voltage field
            current_load=current_load,  # Store directly in the current_load field
            observations=observations_text,  # Store observations in the observations field
            date=current_date,  # Store the current date
            created_by=request.user
        )
        checklist.save()
        checklist.full_clean()

        # Save each uploaded attachment
        for attachment in attachments:
            MaintenanceChecklistAttachment.objects.create(checklist=checklist, file=attachment)

        # Redirect after successful save (customize as needed)
        return redirect('maintenance_checklist')  # Adjust this to your URL name

    return render(request, 'apage/maintenance_checklist.html', {'machines': machines})





from django.shortcuts import render
from .models import MaintenanceChecklist
# maintenance_checklist_records

def maintenance_checklist(request):
    user = request.user
    user_role = user.groups.first().name if user.groups.first() else None 
    if user.is_superuser or user.is_staff:
        user_role = 'Admin'
    if user_role == 'Admin':
        checklists = MaintenanceChecklist.objects.all().order_by('-date')
    else:
        checklists = MaintenanceChecklist.objects.filter(created_by=user).order_by('-date')  # Order by most recent
    query = request.GET.get('search', '')
    if query:
        checklists = checklists.filter(
            # Q(inspector_name__icontains=query) |
                Q(date__icontains=query) |
                Q(machine__name__icontains=query) |
                Q(visit_date__icontains=query) |
                Q(observations__icontains=query)
        )

    context = {
        'checklists': checklists,
        'search_query': query,
    }
    return render(request, 'apage/maintenance_checklist_viewing.html', context)

from django.shortcuts import render, get_object_or_404, redirect
from .models import MaintenanceChecklist, Machine, MaintenanceChecklistAttachment

def edit_maintenance_checklist(request, id):
    # Get the checklist record or return 404 if not found
    checklist = get_object_or_404(MaintenanceChecklist, id=id)

    if request.method == 'POST':
        # Update checklist fields
        checklist.inspector_name = request.POST.get('inspector_name', checklist.inspector_name)
        checklist.date = request.POST.get('date', checklist.date)
        checklist.visit_date = request.POST.get('visit_date', checklist.visit_date)

        # Handle supply_voltage (checkboxes)
        checklist.supply_voltage = request.POST.getlist('supply_voltage')  # This will return a list of selected values
        checklist.supply_voltage_details = request.POST.get('supply_voltage_details', checklist.supply_voltage)

        # Handle current_load (checkboxes)
        checklist.current_load = request.POST.getlist('current_load')  # This will return a list of selected values
        checklist.current_load_details = request.POST.get('current_load_details', checklist.current_load)

        # Handle observations (array of observations)
        observations = request.POST.getlist('observation[]')  # This retrieves a list of observations
        checklist.observations = '\n'.join(observations)  # Join them with a newline for easy readability

        for attachment in checklist.attachments.all():
            remove_key = f"remove_attachment_{attachment.id}"
            if remove_key in request.POST:
                attachment.delete()


        # Update the machine field if provided
        machine_id = request.POST.get('machine_name')
        if machine_id:
            checklist.machine = get_object_or_404(Machine, id=machine_id)

        checklist.save()

        # Handle the uploaded attachments
        files = request.FILES.getlist('attachment[]')  # Make sure this matches the form input name
        for file in files:
            MaintenanceChecklistAttachment.objects.create(checklist=checklist, file=file)

        # Redirect to the maintenance checklist records page
        return redirect('maintenance_checklist')

    # Fetch machines and existing attachments
    machines = Machine.objects.all()
    attachments = checklist.attachments.all()  # Correctly fetch attachments using `related_name`

    # Render the edit page with all required data
    return render(request, 'apage/edit_maintenance_checklist.html', {
        'checklist': checklist,
        'machines': machines,
        'attachments': attachments,
        'supply_voltage': checklist.supply_voltage,
        'current_load': checklist.current_load,
        'observations': checklist.observations,
    })

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
# # from weasyprint import HTML
from .models import MaintenanceChecklist

def pdf_maintenance_checklist(request, checklist_id):
    # Fetch the checklist record by ID
    checklist = get_object_or_404(MaintenanceChecklist, pk=checklist_id)

    # Render the HTML template for the checklist
    html_content = render_to_string('apage/pdf_maintenance_checklist.html', {'checklist': checklist})

    # Return the PDF response as a downloadable file
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=maintenance_checklist_{checklist.id}.pdf'

    pisa_status = pisa.CreatePDF(html_content, dest=response, link_callback=link_callback)
    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)
    return response




# -----------------------------MOM-----------------------------------


def mom_details_with_history(request, mom_id):
    # Retrieve the MOM instance
    mom = get_object_or_404(MOM, id=mom_id)

    # Render the details and history
    return render(request, 'apage/edithistory_mom.html', {'mom': mom})

from django.shortcuts import render, redirect
from .models import MOM, Attachment
from django.utils.timezone import now

def mom(request):
    user=request.user
    user_role = user.groups.first().name if user.groups.first() else None
    if user.is_superuser or user.is_staff:
        user_role = 'Admin'
    # Fetch all MOM records ordered by the most recent
    if user_role == 'Admin':
        mom_records = MOM.objects.all().order_by('-id')
    else:
        mom_records = MOM.objects.filter(created_by=request.user).order_by('-id')  # Adjust the order as needed

    search_query = request.GET.get('search', '')
    if search_query:
        mom_records = mom_records.filter(
            Q(topic__icontains=search_query) |
            Q(organize__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(meeting_chair__icontains=search_query) |
            Q(date__icontains=search_query)
        )

    context = {
        'mom_records': mom_records,
        'search_query': search_query,
    }
    return render(request, 'apage/mom_viewing.html', context)
    


from django.shortcuts import render, redirect
from .models import MOM, Attachment
from django.core.exceptions import ValidationError

@login_required
def mom_new(request):
    if request.method == 'POST':
        # Create the meeting instance from POST data
        meeting = MOM(
            topic=request.POST.get('topic', ''),
            organize=request.POST.get('organize', ''),
            meeting_chair=request.POST.get('meeting_chair', ''),
            location=request.POST.get('location', ''),
            date=request.POST.get('mdate'),
            start_time=request.POST.get('start_time'),
            end_time=request.POST.get('end_time'),
            duration=request.POST.get('duration', ''),
            updated_by=request.user.username,  # Set logged-in user as the updater
            meeting_conclusion=request.POST.get('meeting_conclusion', ''),
            summary_of_discussion=request.POST.get('summary_of_discussion', ''),
            attendees=request.POST.getlist('attendees[]'),
            apologies=request.POST.getlist('apologies[]'),
            agenda=request.POST.getlist('agenda[]'),
            created_by=request.user
        )

        try:
            meeting.full_clean()
            meeting.save()
            
            # Save the uploaded files (attachments)
            for attachment_file in request.FILES.getlist('attachment[]'):
                attachment = Attachment(file=attachment_file, meeting=meeting)
                attachment.save()

            # Redirect to the mom_viewing page with the newly created meeting's ID
            return redirect('mom')
        except ValidationError as e:
            return render(request, 'apage/mom.html', {'error': e.message_dict})

    # If the request is not POST, render the form page
    return render(request, 'apage/mom.html')

    

def mom_detail(request, mom_id):
    mom = get_object_or_404(MOM, id=mom_id)
    return render(request, 'apage/mom_detail.html', {'mom': mom})

# views.py

from django.shortcuts import render, get_object_or_404, redirect
from .models import MOM, Attachment

def mom_edit(request, mom_id):
    # Fetch the MOM record to be edited
    mom = get_object_or_404(MOM, id=mom_id)
    print(f"dr,{mom.duration}")
    if request.method == 'POST':
        # Update the meeting instance with the new data from POST
        mom.topic = request.POST.get('topic', '')
        mom.organize = request.POST.get('organize', '')
        mom.meeting_chair = request.POST.get('meeting_chair', '')
        mom.location = request.POST.get('location', '')
        mom.date = request.POST.get('mdate')
        mom.start_time = request.POST.get('start_time')
        mom.end_time = request.POST.get('end_time')
        mom.duration = request.POST.get('duration', '')
        mom.updated_by = request.user.username  # Set the logged-in user as the updater
        mom.meeting_conclusion = request.POST.get('meeting_conclusion', '')
        mom.summary_of_discussion = request.POST.get('summary_of_discussion', '')
        mom.attendees = request.POST.getlist('attendees[]')
        mom.apologies = request.POST.getlist('apologies[]')
        mom.agenda = request.POST.getlist('agenda[]')

        try:
            mom.full_clean()
            mom.save()

            # Handle file attachments
            for attachment_file in request.FILES.getlist('attachment[]'):
                attachment = Attachment(file=attachment_file, meeting=mom)
                attachment.save()

            # Redirect to the MOM detail page after saving the changes
            return redirect('mom_detail', mom_id=mom.id)
        except ValidationError as e:
            return render(request, 'apage/edit_mom.html', {'mom': mom, 'error': e.message_dict})

    # If the request is not POST, display the edit form with existing data
    return render(request, 'apage/edit_mom.html', {'mom': mom})


from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
# # from weasyprint import HTML

def pdf_mom(request, mom_id):
    # Fetch the MOM record by ID
    mom = get_object_or_404(MOM, pk=mom_id)

    # Render the HTML content to be converted to PDF
    html_content = render_to_string('apage/pdf_mom.html', {'mom': mom})

    # Return the PDF response as a downloadable file
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=mom_{mom.id}.pdf'

    pisa_status = pisa.CreatePDF(html_content, dest=response, link_callback=link_callback)
    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)
    return response




# --------------------------generalreport-----------------------------

from django.shortcuts import render, redirect

from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect
from .models import Site, GeneralReport
from django.shortcuts import render, get_object_or_404

def view_edit_history(request, report_id):
    report = get_object_or_404(GeneralReport, id=report_id)
    return render(request, 'apage/edithistory_generalreport.html', {'report': report})

@login_required
def generalreportsnew(request):
    sites = Site.objects.all()  # Get all available sites
    if request.method == 'POST':
        # Fetch the Site instance by ID from the POST data
        site_id = request.POST.get('site')
        try:
            site_instance = Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            return render(request, 'apage/error_template.html', {'error': 'Invalid site selected'})

        # Create a GeneralReport instance without saving to the database
        report = GeneralReport(
            site=site_instance,
            date_of_visit=request.POST.get('date_of_visit'),
            point1=request.POST.get('point1'),
            point2=request.POST.get('point2'),
            point3=request.POST.get('point3'),
            point4=request.POST.get('point4'),
            notes=request.POST.get('notes'),
            attachment=request.FILES.get('attachment'),
            created_by=request.user
        )

        # Validate the report instance
        try:
            if not report.is_draft:
                report.full_clean()  # Only validate if it's not a draft
            report.save()  # Always save
        except ValidationError as e:
            return render(request, 'apage/generalreport.html', {
                'reports': GeneralReport.objects.all(),
                'sites': sites,
                'error': e.message_dict
            })

        # Redirect to the viewing page after successful save
        return redirect('generalreport')  # Ensure this URL name is correct

    # Fetch all saved reports to display
    reports = GeneralReport.objects.all()
    return render(request, 'apage/generalreport.html', {'reports': reports, 'sites': sites})



from django.db.models import Q

def generalreport(request):
    query = request.GET.get('search', '')
    current_user = request.user

    # Privileged users see all reports; others see only their own
    if current_user.is_staff or current_user.is_superuser:
        reports = GeneralReport.objects.all().order_by('-id')
    else:
        reports = GeneralReport.objects.filter(created_by=current_user).order_by('-id')

    # Search filter
    if query:
        reports = reports.filter(
            Q(site__name__icontains=query) |
            Q(date_of_visit__icontains=query) |
            Q(point1__icontains=query) |
            Q(point2__icontains=query) |
            Q(point3__icontains=query) |
            Q(point4__icontains=query) |
            Q(notes__icontains=query)
        )

    context = {
        'reports': reports,
        'search_query': query,
    }
    return render(request, 'apage/generalreportviewing.html', context)

from django.shortcuts import render, get_object_or_404, redirect


def edit_general_report(request, report_id):
    report = get_object_or_404(GeneralReport, id=report_id)
    sites = Site.objects.all()  # For the site selection dropdown

    if request.method == 'POST':
        # Fetch the updated data from the form
        site_id = request.POST.get('site')
        try:
            site_instance = Site.objects.get(id=site_id)
        except Site.DoesNotExist:
            return render(request, 'apage/error_template.html', {'error': 'Invalid site selected'})

        # Update the GeneralReport instance
        report.site = site_instance
        report.date_of_visit = request.POST.get('date_of_visit')
        report.point1 = request.POST.get('point1')
        report.point2 = request.POST.get('point2')
        report.point3 = request.POST.get('point3')
        report.point4 = request.POST.get('point4')
        report.notes = request.POST.get('notes')

        # Update attachment if a new file is uploaded
        if request.FILES.get('attachment'):
            report.attachment = request.FILES.get('attachment')

        try:
            # Only validate if it's a final save (not a draft or partial update)
            if not getattr(report, "is_draft", False):
                report.full_clean()
            report.save()  # Save even if full_clean() is skipped
        except ValidationError as e:
            # Handle validation errors (e.g., future date, required fields, etc.)
            return render(request, 'apage/edit_general_report.html', {
                'report': report,
                'sites': sites,
                'error': e.message_dict  # optional: show in template
            })

        return redirect('generalreport')  # Redirect after successful save


from django.shortcuts import get_object_or_404, render
from django.http import HttpResponse
# # from weasyprint import HTML


def generate_report_pdf(request, report_id):
    # Fetch the report based on its ID
    report = get_object_or_404(GeneralReport, pk=report_id)

    # Render the HTML content to be converted to PDF
    html_content = render_to_string('apage/pdf_generalreport.html', {'report': report})

    # Return the PDF response as a downloadable file
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=general_report_{report.id}.pdf'

    pisa_status = pisa.CreatePDF(html_content, dest=response, link_callback=link_callback)
    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)
    return response


# ------------servicereport--------------------

@csrf_exempt
def service_reports_api(request):
    """
    Dedicated JSON API endpoint for the Flutter app to fetch service reports.
    Authenticates via the 'Authorization: Token ...' header.
    """
    if request.method != 'GET':
        return JsonResponse({"status": "error", "message": "Method not allowed"}, status=405)

    user = get_user_from_request(request)
    if user.is_anonymous:
        return JsonResponse({"status": "error", "message": "Authentication required. Please provide a valid Token."}, status=401)

    # Exactly mimic the website's role checking
    is_admin = user.groups.filter(name='Admin').exists() or user.is_staff or user.is_superuser

    if is_admin:
        service_reports = ServiceReport.objects.filter(is_draft=False)
    else:
        service_reports = ServiceReport.objects.filter(created_by=user, is_draft=False)

    groups = [g.name for g in user.groups.all()]
    # 🐛 DEBUG: Comprehensive diagnostic check
    total_count = ServiceReport.objects.count()
    draft_count = ServiceReport.objects.filter(is_draft=True).count()
    final_count = ServiceReport.objects.filter(is_draft=False).count()
    user_final_count = ServiceReport.objects.filter(created_by=user, is_draft=False).count()
    
    print(f"--- API DIAGNOSTIC for {user.username} ---")
    print(f"Admin: {is_admin}")
    print(f"Total ServiceReport objects in DB: {total_count}")
    print(f"Drafts (is_draft=True): {draft_count}")
    print(f"Finalized (is_draft=False): {final_count}")
    print(f"Finalized & Created By this user: {user_final_count}")
    print(f"Returning {service_reports.count()} reports based on logic.")
    print(f"----------------------------------------")

    service_reports = service_reports.order_by('-date_of_visit')
    reports_data = []
    for report in service_reports:
        try:
            # Fetch related items
            electronic_items = []
            for s in ElectronicItemStatus.objects.filter(report=report):
                electronic_items.append({
                    'status_id': s.id,
                    'item_id': s.item.id if s.item else '',
                    'item_name': s.item.name if s.item else '',
                    'checked': s.checked,
                    'repair': s.repair,
                    'replacement': s.replacement,
                    'remark': s.remark
                })

            panel_items = []
            for s in ElectronicPanelStatus.objects.filter(report=report):
                panel_items.append({
                    'status_id': s.id,
                    'item_id': s.panel.id if s.panel else '',
                    'item_name': s.panel.name if s.panel else '',
                    'checked': s.checked,
                    'repair': s.repair,
                    'replacement': s.replacement,
                    'remark': s.remark
                })

            chemical_items = []
            for s in ChemicalItemStatus.objects.filter(report=report):
                chemical_items.append({
                    'status_id': s.id,
                    'item_id': s.item.id if s.item else '',
                    'item_name': s.item.name if s.item else '',
                    'checked': s.checked,
                    'repair': s.repair,
                    'replacement': s.replacement,
                    'remark': s.remark
                })

            pump_items = []
            for s in PumpStatus.objects.filter(report=report):
                pump_items.append({
                    'status_id': s.id,
                    'item_id': s.pump.id if s.pump else '',
                    'item_name': s.pump.name if s.pump else '',
                    'checked': s.checked,
                    'repair': s.repair,
                    'replacement': s.replacement,
                    'remark': s.remark
                })

            misc_items = []
            for s in MiscellaneousItemStatus.objects.filter(report=report):
                misc_items.append({
                    'status_id': s.id,
                    'item_id': s.item.id if s.item else '',
                    'item_name': s.item.name if s.item else '',
                    'checked': s.checked,
                    'repair': s.repair,
                    'replacement': s.replacement,
                    'remark': s.remark
                })

            wastewater_items = []
            for s in WastewaterParameterStatus.objects.filter(report=report):
                wastewater_items.append({
                    'status_id': s.id,
                    'item_id': s.parameter.id if s.parameter else '',
                    'item_name': s.parameter.name if s.parameter else '',
                    'checked': s.checked,
                    'repair': s.repair,
                    'replacement': s.replacement,
                    'remark': s.remark
                })

            run_cycles = []
            for s in MachineRunTime.objects.filter(service_report=report):
                run_cycles.append({
                    'id': s.id,
                    'run_time': str(s.run_time) if s.run_time else '',
                    'end_time': str(s.end_time) if s.end_time else '',
                    'checked': s.checked,
                    'pass_run': s.pass_status,
                    'fail_run': s.fail_status,
                    'remark': s.remark
                })

            tool_kits = []
            for s in ToolStatus.objects.filter(service_report=report):
                tool_kits.append({
                    'status_id': s.id,
                    'item_id': s.tool.id if s.tool else '',
                    'item_name': s.tool.name if s.tool else '',
                    'quantity': s.quantity,
                    'remark': s.remark,
                    'taken_status': s.taken_status
                })

            attachments = []
            for a in ServiceReportAttachment.objects.filter(service_report=report):
                attachments.append({
                    'id': a.id,
                    'file_url': a.file.url if a.file else '',
                    'name': a.file.name if a.file else ''
                })

            reports_data.append({
                'id': report.id,
                'service_name': getattr(report, 'service_name', ''),
                'date_of_visit': str(report.date_of_visit) if getattr(report, 'date_of_visit', None) else '',
                'zone': report.zone.id if (hasattr(report, 'zone') and report.zone) else '',
                'zone_name': report.zone.name if (hasattr(report, 'zone') and report.zone) else '',
                'site': report.site.id if (hasattr(report, 'site') and report.site) else '',
                'site_name': report.site.name if (hasattr(report, 'site') and report.site) else '',
                'phone_no': getattr(report, 'phone_no', ''),
                'reason_of_visit': getattr(report, 'reason_of_visit', ''),
                'in_time': str(report.in_time) if getattr(report, 'in_time', None) else '',
                'out_time': str(report.out_time) if getattr(report, 'out_time', None) else '',
                'customer_name': getattr(report, 'customer_name', ''),
                'contact_number': getattr(report, 'contact_number', ''),
                'location': getattr(report, 'location', ''),
                'state': report.state.name if (hasattr(report, 'state') and report.state) else '',
                'state_id': report.state.id if (hasattr(report, 'state') and report.state) else '',
                'date_of_complaint': str(report.date_of_complaint) if getattr(report, 'date_of_complaint', None) else '',
                'status_of_call': getattr(report, 'status_of_call', ''),
                'status': getattr(report, 'status', 'pending'),
                'rejection_reason': getattr(report, 'rejection_reason', ''),
                'service_person_name': getattr(report, 'service_person_name', ''),
                'client_name': getattr(report, 'client_name', ''),
                'service_person_signature': getattr(report, 'service_person_signature', ''),
                'client_signature': getattr(report, 'client_signature', ''),
                'created_at': report.created_date.isoformat() if getattr(report, 'created_date', None) else '',
                'other_remarks': getattr(report, 'other_remarks', ''),
                'spares_details': getattr(report, 'spares_details', ''),
                # Related items
                'electronic_items': electronic_items,
                'panel_items': panel_items,
                'chemical_items': chemical_items,
                'pump_items': pump_items,
                'misc_items': misc_items,
                'wastewater_items': wastewater_items,
                'run_cycles': run_cycles,
                'tool_kits': tool_kits,
                'attachments': attachments,
            })
        except Exception as e:
            print(f"Error serializing report {report.id}: {e}")
            continue

    return JsonResponse({"status": "success", "is_admin": is_admin, "reports": reports_data})



from django.shortcuts import render, redirect
from .models import ServiceReport, ElectronicItem, ElectronicItemStatus, ElectronicPanel ,ElectronicPanelStatus ,WastewaterParameterStatus
from .models import ChemicalItem ,ChemicalItemStatus ,Pump ,PumpStatus ,MiscellaneousItem ,MiscellaneousItemStatus ,WastewaterParameter
from .models import MachineRunTime ,Tool ,ToolStatus ,State
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, authentication_classes, permission_classes, parser_classes
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q
from django.core.exceptions import ObjectDoesNotExist  # Import the exception
from django.http import JsonResponse


def safe_get_or_create(model, **kwargs):
    qs = model.objects.filter(**kwargs)
    first_obj = qs.first()
    
    # If duplicates exist, return the first one safely
    if first_obj:
        return first_obj, False

    # If none exists, create one
    return model.objects.create(**kwargs), True



def get_service_report_permissions(user):
    """
    Returns granular permissions for Service Reports:
    - Admin: View All, Create, Edit, Approve/Reject, Download, Edit History
    - Service Manager: View All, Create, Edit, Approve/Reject, Download
    - Service Engineer: View All, Create, Download (NO Edit, NO Approve/Reject)
    - Default / Other: Own Reports only, Create, Edit, Download (NO Approve/Reject)
    """
    if not user or not user.is_authenticated:
        return {
            'can_view_all': False,
            'can_create': False,
            'can_edit': False,
            'can_approve_reject': False,
            'can_download': False,
            'role': None,
        }

    is_admin = user.is_superuser or user.is_staff or user.groups.filter(name='Admin').exists()
    is_manager = is_admin or user.groups.filter(name='Service Manager').exists()
    is_engineer = user.groups.filter(name='Service Engineer').exists()

    profile = getattr(user, 'userprofile', None)
    profile_can_edit = True
    if profile is not None and hasattr(profile, 'can_edit_service_reports'):
        profile_can_edit = profile.can_edit_service_reports

    if user.groups.filter(name__in=['Service Report - View Only', 'Disable Service Report Edit', 'No Edit Service Report']).exists():
        profile_can_edit = False

    if is_admin:
        return {
            'can_view_all': True,
            'can_create': True,
            'can_edit': True if profile_can_edit else False,
            'can_approve_reject': True,
            'can_download': True,
            'role': 'Admin',
        }
    elif is_manager:
        return {
            'can_view_all': True,
            'can_create': True,
            'can_edit': True if profile_can_edit else False,
            'can_approve_reject': True,
            'can_download': True,
            'role': 'Service Manager',
        }
    elif is_engineer:
        return {
            'can_view_all': True,           # Service Engineer sees ALL reports
            'can_create': True,             # Everyone can create reports
            'can_edit': False,              # Service Engineer CANNOT edit
            'can_approve_reject': False,    # Service Engineer CANNOT approve/reject
            'can_download': True,           # View & Download allowed
            'role': 'Service Engineer',
        }
    else:
        # Default / Regular User
        return {
            'can_view_all': False,          # Only sees reports they created
            'can_create': True,
            'can_edit': True if profile_can_edit else False,
            'can_approve_reject': False,
            'can_download': True,
            'role': 'User',
        }


def can_user_edit_service_report(user):
    return get_service_report_permissions(user)['can_edit']



@login_required
def servicereport(request):
    search_query = request.GET.get('search', '')
    user_filter = request.GET.get('user', '')
    site_filter = request.GET.get('site', '')

    user = request.user
    sr_perms = get_service_report_permissions(user)
    user_role = sr_perms['role']

    # Base queryset: Admin, Service Manager, and Service Engineer see all reports
    if sr_perms['can_view_all']:
        service_reports = ServiceReport.objects.all()
    else:
        service_reports = ServiceReport.objects.filter(created_by=user)
        
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    if start_date:
        service_reports = service_reports.filter(date_of_visit__gte=start_date)
    if end_date:
        service_reports = service_reports.filter(date_of_visit__lte=end_date)

    # 🔍 Search filter
    if search_query:
        service_reports = service_reports.filter(
            Q(service_name__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(state__name__icontains=search_query) |
            Q(status_of_call__icontains=search_query) |
            Q(site__name__icontains=search_query)
        )

    # 👤 User filter (for users who can view all)
    if user_filter and sr_perms['can_view_all']:
        service_reports = service_reports.filter(created_by__id=user_filter)

    # 🏢 Site filter
    if site_filter:
        service_reports = service_reports.filter(site__id=site_filter)

    service_reports = service_reports.order_by('-date_of_visit')

    context = {
        'service_reports': service_reports,
        'search_query': search_query,
        'selected_user': user_filter,
        'selected_site': site_filter,
        'user_role': user_role,
        'sr_perms': sr_perms,
        'users': User.objects.all() if sr_perms['can_view_all'] else [],
        'sites': Site.objects.all(),
        'start_date': start_date,
        'end_date': end_date,
        'can_edit_service_reports': sr_perms['can_edit'],
    }
    return render(request, 'apage/servicereport_viewing.html', context)

# views.py
from django.shortcuts import render
from .models import ServiceReport ,ServiceReportAttachment
from app.models import Zone
from website.models import Notification
from datetime import timedelta

from django.views.decorators.csrf import csrf_exempt

def get_user_from_request(request):
    """Manually checks for a DRF Token in the Authorization header to authenticate requests from the Flutter app."""
    if not request.user.is_anonymous:
        return request.user

    auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION')
    if auth_header and auth_header.startswith('Token '):
        token_key = auth_header.split(' ')[1]
        try:
            from rest_framework.authtoken.models import Token
            token = Token.objects.get(key=token_key)
            print(f"DEBUG: Manually authenticated user: {token.user.username}")
            return token.user
        except Exception as e:
            print("Token validation error:", e)
            print(f"DEBUG: Token validation failure for {token_key[:10]}...: {e}")
            pass
    return request.user

@csrf_exempt
def service_report_new(request):
    user = get_user_from_request(request)
    if user.is_anonymous:
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION', '')
        is_api = auth_header.startswith('Token ') or request.headers.get('Accept') == 'application/json' or request.content_type == 'application/json'
        if is_api:
            return JsonResponse({"status": "error", "message": "Authentication required. Please login again."}, status=401)
        return redirect('login')

    tools = Tool.objects.all()
    state_name = request.POST.get("state")
    state_instance = State.objects.get(name=state_name) if state_name else None
    service_report = None  # Initialize service_report to None
    zones = Zone.objects.all()



    if request.method == 'POST':
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION', '')
        is_api = auth_header.startswith('Token ') or request.headers.get('Accept') == 'application/json' or request.content_type == 'application/json'
        print("post data :",request.POST)
        # Static fields from the form (using .get() with default values to avoid errors)
        service_name = request.POST.get('service_name', '')
        date_of_visit = parse_date(request.POST.get('date_of_visit'))
        zone_id = request.POST.get('zone')
        site_id = request.POST.get('site')
        phone_no = request.POST.get('phone_no', '')
        reason_of_visit = request.POST.get('reason_of_visit', '')
        in_time = request.POST.get('in_time', '')
        out_time = request.POST.get('out_time', '')

        # Customer Information
        customer_name = request.POST.get('customer_name', '')
        contact_number = request.POST.get('contact_number', '')
        location = request.POST.get('location', '')
        state = request.POST.get('state', '')
        date_of_complaint = request.POST.get('date_of_complaint', '')
        status_of_call = request.POST.get('status_of_call', '')
        service_person_signature = request.POST.get('service_person_signature', '')
        service_person_name = request.POST.get('service_person_name', '')
        client_signature = request.POST.get('client_signature', '')
        client_name = request.POST.get('client_name', '')
        # Create the ServiceReport


        try:
            zone = Zone.objects.get(id=zone_id) if zone_id else None
            site = Site.objects.get(id=site_id) if site_id else None
        except ObjectDoesNotExist:
            messages.error(request, 'Invalid Zone or Site selected.')
            if is_api:
                return JsonResponse({"status": "error", "message": "Invalid Zone or Site selected."}, status=400)
            return redirect('service_report_new')
        


        # Manually authenticate user for API calls
        user = get_user_from_request(request)
        if user.is_anonymous:
            if is_api:
                return JsonResponse({"status": "error", "message": "Authentication required. Please login again."}, status=401)
            return redirect('login') # Or wherever unauthenticated web users go


        service_report = ServiceReport.objects.filter(
            created_by=user,
            site=site,
            date_of_visit=date_of_visit,
            is_draft=True
        ).first()

        if service_report:
            # Finalize existing CONTEXT draft
            service_report.service_name = service_name
            service_report.date_of_visit = date_of_visit
            service_report.zone = zone
            service_report.site = site
            service_report.phone_no = phone_no
            service_report.reason_of_visit = reason_of_visit
            service_report.in_time = in_time
            service_report.out_time = out_time
            service_report.customer_name = customer_name
            service_report.contact_number = contact_number
            service_report.location = location
            service_report.state = state_instance
            service_report.date_of_complaint = date_of_complaint
            service_report.status_of_call = status_of_call
            service_report.service_person_signature = service_person_signature
            service_report.service_person_name = service_person_name
            service_report.client_signature = client_signature
            service_report.client_name = client_name
            service_report.is_draft = False  # 🔒 LOCK
            service_report.save()
            
        else:
            service_report = ServiceReport.objects.create(
                service_name=service_name,
                date_of_visit=date_of_visit,
                zone=zone,
                site=site,
                phone_no=phone_no,
                reason_of_visit=reason_of_visit,
                in_time=in_time,
                out_time=out_time,
                customer_name=customer_name,
                contact_number=contact_number,
                location=location,
                state=state_instance,
                date_of_complaint=date_of_complaint,
                status_of_call=status_of_call,
                service_person_signature=service_person_signature,
                service_person_name=service_person_name,
                client_signature=client_signature,
                client_name=client_name,
                created_by=user,
                is_draft=False,
            )

        # 🔒 Duplicate prevention BEFORE photo processing
        existing_report = ServiceReport.objects.filter(
            created_by=user,
            date_of_visit=date_of_visit,
            site=site,
            is_draft=False
        ).exclude(id=service_report.id).first()

        if existing_report:
            messages.warning(request, "A service report for this site and date already exists.")
            if is_api:
                return JsonResponse({"status": "error", "message": "A service report for this site and date already exists."}, status=400)
            return redirect('servicereport')

        # Handle multiple files from both fields (Standardized keys)
        for field in ['attachment_1', 'attachment_2', 'attachments1', 'attachments2']:
            for file in request.FILES.getlist(field):
                ServiceReportAttachment.objects.create(
                    service_report=service_report,
                    file=file
                )

        electronic_panels = ElectronicPanel.objects.all()
        electronic_items = ElectronicItem.objects.all()
        chemical_items = ChemicalItem.objects.all()
        pumps = Pump.objects.all()
        miscellaneous_items = MiscellaneousItem.objects.all()
        wastewater_parameters = WastewaterParameter.objects.all()
        machine_runtimes =MachineRunTime.objects.all()
        states = State.objects.all()  # Get all states from the database
        remarks = []
        spares = []
        # Collect all remarks from form data
        for key, value in request.POST.items():
            if key.startswith('remark_orm_') and value.strip():
                remarks.append(value.strip())
                # Collect spares details
        for key, value in request.POST.items():
            if key.startswith('spare_') and value.strip():
                spares.append(value.strip())


        # Join all remarks into a single string separated by newlines
        service_report.other_remarks = '\n'.join(remarks)
        service_report.spares_details = '\n'.join(spares)

        try:
            if not getattr(service_report, "is_draft", False):  # Only validate if not draft
                service_report.full_clean()  # Will raise ValidationError if any
            service_report.save()
            
            # --- Safe scheduling and notification ---
            if service_report.site and service_report.date_of_visit:
                try:
                    due_date = service_report.date_of_visit + timedelta(days=15)
                    Notification.objects.create(
                        user=request.user,
                        title=f" Second Service Visit Due for {service_report.site.name}",
                        message=f"A follow-up service visit is required at {service_report.site.name} by {due_date.strftime('%d %b %Y')}.",
                    )
                    update_site_schedule(service_report.site, service_report.date_of_visit)
                except Exception as scheduler_err:
                    print(f"Scheduling error (non-critical): {scheduler_err}")
            
        except ValidationError as e:
            # Handle or log the validation error if needed
            print("Validation failed during final save:", e.message_dict)
        # Handle dynamic electronic items and their statuses
        for item in electronic_items:
            checked = request.POST.get(f'checked_{item.id}') == 'on'
            repair = request.POST.get(f'repair_{item.id}') == 'on'
            replacement = request.POST.get(f'replacement_{item.id}') == 'on'
            remark = request.POST.get(f'remark_eitems_{item.id}')

            # Create an entry in ElectronicItemStatus for each item
            ElectronicItemStatus.objects.update_or_create(
                report=service_report,
                item=item,
                defaults={
                    "checked": checked,
                    "repair": repair,
                    "replacement": replacement,
                    "remark": remark,
                }
            )
            

        # Handle dynamic electronic panels and their statuses
        for panel in electronic_panels:
            checked = request.POST.get(f'checked_{panel.id}') == 'on'
            repair = request.POST.get(f'repair_{panel.id}') == 'on'
            replacement = request.POST.get(f'replacement_{panel.id}') == 'on'
            remark = request.POST.get(f'remark_epanels_{panel.id}')

            # Create an entry in ElectronicPanelStatus for each panel
            ElectronicPanelStatus.objects.update_or_create(
                report=service_report,
                panel=panel,
                defaults={
                "checked" : checked,
                "repair" : repair,
                "replacement" : replacement,
                "remark" : remark,
                 }
            )

        
        for item in chemical_items:
            checked = request.POST.get(f'checked_chemical_{item.id}') == 'on'
            repair = request.POST.get(f'repair_chemical_{item.id}') == 'on'
            replacement = request.POST.get(f'replacement_chemical_{item.id}') == 'on'
            remark = request.POST.get(f'remark_chemical_{item.id}')

            # Create ChemicalItemStatus entry
            ChemicalItemStatus.objects.update_or_create(
                report=service_report,
                item=item,
                defaults={
                "checked" : checked,
                "repair" : repair,
                "replacement" : replacement,
                "remark" : remark,
                 }
            )

        for pump in pumps:
            checked = request.POST.get(f'checked_pump_{pump.id}') == 'on'
            repair = request.POST.get(f'repair_pump_{pump.id}') == 'on'
            replacement = request.POST.get(f'replacement_pump_{pump.id}') == 'on'
            remark = request.POST.get(f'remark_pump_{pump.id}')

            # Create PumpStatus entry
            PumpStatus.objects.update_or_create(
                report=service_report,
                pump=pump,
                defaults={
                "checked" : checked,
                "repair" : repair,
                "replacement" : replacement,
                "remark" : remark,
                 }
            )

        for item in miscellaneous_items:
            checked = request.POST.get(f'checked_miscellaneous_{item.id}') == 'on'
            repair = request.POST.get(f'repair_miscellaneous_{item.id}') == 'on'
            replacement = request.POST.get(f'replacement_miscellaneous_{item.id}') == 'on'
            remark = request.POST.get(f'remark_miscellaneous_{item.id}')

            # Create MiscellaneousItemStatus entry
            MiscellaneousItemStatus.objects.update_or_create(
                report=service_report,
                item=item,
                defaults={
                "checked" : checked,
                "repair" : repair,
                "replacement" : replacement,
                "remark" : remark,
                 }
            )
        
        for parameter in wastewater_parameters:
            checked = request.POST.get(f'checked_wastewater_{parameter.id}') == 'on'
            repair = request.POST.get(f'repair_wastewater_{parameter.id}') == 'on'
            replacement = request.POST.get(f'replacement_wastewater_{parameter.id}') == 'on'
            remark = request.POST.get(f'remark_wastewater_{parameter.id}')

            # Create WastewaterParameterStatus entry
            WastewaterParameterStatus.objects.update_or_create(
                report=service_report,
                parameter=parameter,
                defaults={
                "checked" : checked,
                "repair" : repair,
                "replacement" : replacement,
                "remark" : remark,
                 }
            )
        

        #Machine Run Time.
        run_cycle_count = int(request.POST.get('run_cycle_count', 1))
        rc = run_cycle_count+1
        for cycle_number in range(1, rc):
            print(cycle_number)
            # Get data for each cycle (this assumes you have added the fields for each run cycle)
            run_time = request.POST.get(f'run_time_{cycle_number}')
            end_time = request.POST.get(f'end_time_{cycle_number}')
            if not run_time or not end_time:
                continue  
            checked =request.POST.get(f'checked_run_{cycle_number}') == "on"
            pass_status =request.POST.get(f'pass_run_{cycle_number}') == "on"
            fail_status = request.POST.get(f'fail_run_{cycle_number}') == "on"
            remark = request.POST.get(f'remark_run_{cycle_number}')

            print(f"Cycle {cycle_number}: {run_time}, {end_time}, {checked}, {pass_status}, {fail_status}, {remark}")
            


            # Create a new run cycle entry in the database
            MachineRunTime.objects.update_or_create(
                service_report=service_report,
                run_type=f'Run cycle {cycle_number}',
                defaults={
                    "run_time": run_time,
                    "end_time": end_time,
                    "checked": checked,
                    "pass_status": pass_status,
                    "fail_status": fail_status,
                    "remark": remark,
                }
            )
        
        for tool in tools:
            quantity = request.POST.get(f'quantity_{tool.id}')
            remark = request.POST.get(f'remark_tools_{tool.id}')
            taken_status = request.POST.get(f'taken_status_{tool.id}') == 'on'
            print(f"Tool {tool.name}: {quantity}, {remark}")
            
            # Only create the record if quantity is provided
            if quantity:
                ToolStatus.objects.update_or_create(
                    tool=tool,
                    service_report=service_report,
                    defaults={
                        "quantity": int(quantity),
                        "remark": remark,
                        "taken_status": taken_status,
                    }
                )

        # Redundant attachment blocks removed (moved to unified block above)

        if is_api:
            attachments = []
            for a in ServiceReportAttachment.objects.filter(service_report=service_report):
                attachments.append({
                    'id': a.id,
                    'file_url': a.file.url if a.file else '',
                    'name': a.file.name if a.file else ''
                })
            return JsonResponse({
                "status": "success", 
                "report_id": service_report.id,
                "attachments": attachments
            })
        
        messages.success(request, "Service report saved successfully.")
        return redirect('servicereport')  # Web success fallback

    else:
        # If the request is GET, fetch all items and panels for the form
        electronic_items = ElectronicItem.objects.all()
        electronic_panels = ElectronicPanel.objects.all()
        chemical_items = ChemicalItem.objects.all()
        pumps = Pump.objects.all()
        miscellaneous_items = MiscellaneousItem.objects.all()
        wastewater_parameters = WastewaterParameter.objects.all()
        machine_runtimes=MachineRunTime.objects.all()
        states = State.objects.all()  # Get all states from the database

    context = {
        # 'service_report': service_report,
        'electronic_items': electronic_items,
        'electronic_panels': electronic_panels,
        'chemical_items': chemical_items,
        'pumps': pumps,
        'miscellaneous_items': miscellaneous_items,
        'wastewater_parameters': wastewater_parameters,
        'machine_runtimes' : machine_runtimes,
        'tools': tools,
        'states': states,
        'zones': zones,
    }
    return render(request, 'apage/servicereport.html', context)

from apage.models import SiteVisitSchedule
from datetime import timedelta

def update_site_schedule(site, date_of_visit):
    if not site or not date_of_visit:
        return

    obj, created = SiteVisitSchedule.objects.update_or_create(
        site=site,
        defaults={
            'last_visit': date_of_visit,
            'next_due': date_of_visit + timedelta(days=15)
        }
    )

def site_visit_schedule_view(request):
    schedules = SiteVisitSchedule.objects.select_related('site').all().order_by('next_due')
    return render(request, 'xp/home.html', {'schedules': schedules})

from django.http import JsonResponse
from django.utils.dateparse import parse_date, parse_time
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import (
    ServiceReport, Zone, Site, State,
    Tool, ToolStatus, MachineRunTime
)

@csrf_exempt
@login_required
def autosave_service_report(request):
    if request.method != "POST":
        return JsonResponse({"status": "error"})

    # ─────────────────────────────
    # 1. Find or create draft 
    # ─────────────────────────────
    report_id = request.POST.get("report_id")
    
    if report_id and report_id.isdigit():
        # If ID is provided, target specifically that report (Edit Mode)
        user = request.user
        is_admin = user.is_superuser or user.is_staff or (user.groups.first() and user.groups.first().name == 'Admin')
        if is_admin:
            report = ServiceReport.objects.filter(id=report_id).first()
        else:
            report = ServiceReport.objects.filter(id=report_id, created_by=user).first()
        if not report:
            return JsonResponse({"status": "error", "message": "Report not found or permission denied"})
    else:
        # Resolve CONTEXT first for new drafts
        site_id = request.POST.get("site")
        date_of_visit = parse_date(request.POST.get("date_of_visit"))

        if not site_id or not date_of_visit:
            # ⛔ No context → do not autosave
            return JsonResponse({"status": "skipped", "reason": "context_incomplete"})

        site = Site.objects.filter(id=site_id).first()
        if not site:
            return JsonResponse({"status": "skipped", "reason": "invalid_site"})

        # Standard draft resolution by context (New Mode)
        report = ServiceReport.objects.filter(
            created_by=request.user,
            site=site,
            date_of_visit=date_of_visit,
            is_draft=True
        ).first()

        if not report:
            report = ServiceReport.objects.create(
                created_by=request.user,
                site=site,
                date_of_visit=date_of_visit,
                is_draft=True,
                service_name=request.user.username
            )

    # 🔒 Protection: user permission
    if not can_user_edit_service_report(request.user):
        return JsonResponse({"status": "locked", "message": "You do not have permission to edit service reports."})

    # 🔒 Protection: locked reports
    if report.status == 'approved':
        return JsonResponse({"status": "locked", "message": "Approved reports cannot be edited."})
    if not report_id and report.is_draft is False:
        return JsonResponse({"status": "locked"})

def is_valid_drawn_signature(sig):
    if not sig or not isinstance(sig, str):
        return False
    sig = sig.strip()
    if not sig or sig in ("None", "null") or not sig.startswith("data:image"):
        return False
    try:
        import base64
        import io
        from PIL import Image
        _, enc = sig.split(",", 1)
        img = Image.open(io.BytesIO(base64.b64decode(enc)))
        if img.mode == "RGBA":
            alpha = img.split()[-1]
            bbox = alpha.getbbox()
            return bool(bbox and (bbox[2] - bbox[0] > 5 or bbox[3] - bbox[1] > 5))
        extrema = img.convert("L").getextrema()
        return bool(extrema and extrema[0] != extrema[1])
    except Exception:
        return False

    # ─────────────────────────────
    # 3. SAFE field updates (NO ERASE)
    # ─────────────────────────────
    def safe_set(field, value):
        if value not in (None, "", []):
            setattr(report, field, value)

    def safe_set_signature(field, value):
        if is_valid_drawn_signature(value):
            setattr(report, field, value)

    safe_set("customer_name", request.POST.get("customer_name"))
    safe_set("phone_no", request.POST.get("phone_no"))
    safe_set("location", request.POST.get("location"))
    safe_set("reason_of_visit", request.POST.get("reason_of_visit"))
    safe_set("contact_number", request.POST.get("contact_number"))
    safe_set("status_of_call", request.POST.get("status_of_call"))
    safe_set("service_person_name", request.POST.get("service_person_name"))
    safe_set("client_name", request.POST.get("client_name"))
    safe_set_signature("service_person_signature", request.POST.get("service_person_signature"))
    safe_set_signature("client_signature", request.POST.get("client_signature"))

    in_time_val = request.POST.get("in_time")
    if in_time_val:
        report.in_time = parse_time(in_time_val) or report.in_time
    out_time_val = request.POST.get("out_time")
    if out_time_val:
        report.out_time = parse_time(out_time_val) or report.out_time
    doc_val = request.POST.get("date_of_complaint")
    if doc_val:
        report.date_of_complaint = parse_date(doc_val) or report.date_of_complaint

    # Date of visit and Site
    d_visit = request.POST.get("date_of_visit")
    if d_visit:
        report.date_of_visit = parse_date(d_visit) or report.date_of_visit

    site_val = request.POST.get("site")
    if site_val and str(site_val).isdigit():
        report.site = Site.objects.filter(id=site_val).first() or report.site

    # Zone / State (safe)
    if request.POST.get("zone") and str(request.POST.get("zone")).isdigit():
        report.zone = Zone.objects.filter(id=request.POST.get("zone")).first() or report.zone

    state_val = request.POST.get("state")
    if state_val:
        if str(state_val).isdigit():
            report.state = State.objects.filter(id=state_val).first() or report.state
        else:
            report.state = State.objects.filter(name=state_val).first() or report.state

    # Remarks & spares (append-safe)
    remarks = [v.strip() for k, v in request.POST.items() if k.startswith("remark_orm_") and v.strip()]
    spares = [v.strip() for k, v in request.POST.items() if k.startswith("spare_") and v.strip()]

    if remarks:
        report.other_remarks = "\n".join(remarks)

    if spares:
        report.spares_details = "\n".join(spares)

    report.save()

    # ─────────────────────────────
    # 4. Related objects → UPDATE, NEVER DELETE
    # ─────────────────────────────
    save_all_statuses(report, request)   # must use update_or_create internally

    return JsonResponse({
        "status": "saved",
        "report_id": report.id
    })



# ✅ Separately define this below (or in helpers)

from django.utils.dateparse import parse_time

def save_all_statuses(report, request, mode="autosave"):
    from .models import (
        ElectronicItemStatus, ElectronicItem,
        ElectronicPanelStatus, ElectronicPanel,
        ChemicalItemStatus, ChemicalItem,
        PumpStatus, Pump,
        MiscellaneousItemStatus, MiscellaneousItem,
        WastewaterParameterStatus, WastewaterParameter,
        ToolStatus, Tool,
        MachineRunTime,
    )

    # ─────────────────────────────
    # Helper: SAFE update_or_create (NO DELETE)
    # ─────────────────────────────
    def save_category(status_model, field_model, field_attr, checkbox_prefix, remark_prefix):
        for item in field_model.objects.all():
            item_id = str(item.id)

            checked = (
                request.POST.get(f"checked_{checkbox_prefix}_{item_id}") == "on"
                if checkbox_prefix else request.POST.get(f"checked_{item_id}") == "on"
            )
            repair = (
                request.POST.get(f"repair_{checkbox_prefix}_{item_id}") == "on"
                if checkbox_prefix else request.POST.get(f"repair_{item_id}") == "on"
            )
            replacement = (
                request.POST.get(f"replacement_{checkbox_prefix}_{item_id}") == "on"
                if checkbox_prefix else request.POST.get(f"replacement_{item_id}") == "on"
            )
            remark = request.POST.get(f"{remark_prefix}{item_id}", "").strip()

            # ⛔ Do nothing if user has not interacted with this item
            if not any([checked, repair, replacement, remark]):
                continue

            status_model.objects.update_or_create(
                report=report,
                **{field_attr: item},
                defaults={
                    "checked": checked,
                    "repair": repair,
                    "replacement": replacement,
                    "remark": remark,
                }
            )

    # ─────────────────────────────
    # Save all category statuses (SAFE)
    # ─────────────────────────────
    save_category(ElectronicItemStatus, ElectronicItem, "item", "eitems", "remark_eitems_")
    save_category(ElectronicPanelStatus, ElectronicPanel, "panel", "epanels", "remark_epanels_")
    save_category(ChemicalItemStatus, ChemicalItem, "item", "chemical", "remark_chemical_")
    save_category(PumpStatus, Pump, "pump", "pump", "remark_pump_")
    save_category(MiscellaneousItemStatus, MiscellaneousItem, "item", "miscellaneous", "remark_miscellaneous_")
    save_category(WastewaterParameterStatus, WastewaterParameter, "parameter", "wastewater", "remark_wastewater_")

    # ─────────────────────────────
    # Tool Statuses (SAFE)
    # ─────────────────────────────
    for tool in Tool.objects.all():
        tool_id = str(tool.id)
        qty = request.POST.get(f"quantity_{tool_id}", "")
        remark = request.POST.get(f"remark_tools_{tool_id}", "").strip()
        taken = request.POST.get(f"taken_status_{tool_id}") == "on"

        ToolStatus.objects.update_or_create(
            service_report=report,
            tool=tool,
            defaults={
                "quantity": int(qty) if qty.isdigit() else 0,
                "remark": remark,
                "taken_status": taken,
            }
        )

    # ─────────────────────────────
    # Machine Run Times (SAFE)
    # ─────────────────────────────
    # 1. Handle existing MachineRunTime objects by their DB IDs
    for run in MachineRunTime.objects.filter(service_report=report):
        run_time_val = request.POST.get(f"run_time_{run.id}")
        if run_time_val is not None:
            run.run_time = run_time_val or run.run_time
            end_time_val = request.POST.get(f"end_time_{run.id}")
            run.end_time = end_time_val or run.end_time
            run.checked = request.POST.get(f"checked_run_{run.id}") == "on"
            run.pass_status = request.POST.get(f"pass_run_{run.id}") == "on"
            run.fail_status = request.POST.get(f"fail_run_{run.id}") == "on"
            run.remark = request.POST.get(f"remark_run_{run.id}", "").strip()
            run.save()

    # 2. Handle dynamically added run cycles during creation (1..run_cycle_count)
    run_cycle_count = int(request.POST.get("run_cycle_count", 0))
    for i in range(1, run_cycle_count + 1):
        run_time = request.POST.get(f"run_time_{i}")
        end_time = request.POST.get(f"end_time_{i}")

        if not run_time and not end_time:
            continue

        MachineRunTime.objects.update_or_create(
            service_report=report,
            run_type=f"Run cycle {i}",
            defaults={
                "run_time": run_time,
                "end_time": end_time,
                "checked": request.POST.get(f"checked_run_{i}") == "on",
                "pass_status": request.POST.get(f"pass_run_{i}") == "on",
                "fail_status": request.POST.get(f"fail_run_{i}") == "on",
                "remark": request.POST.get(f"remark_run_{i}", "").strip(),
            }
        )

    # 3. Handle newly added runs during edit mode (new_run_time_...)
    new_run_count = int(request.POST.get("new_machine_run_count", 0))
    if new_run_count > 0:
        base_cycle_count = int(request.POST.get("run_cycle_count", 0))
        for i in range(1, new_run_count + 1):
            raw_type = request.POST.get(f"new_run_type_{i}", "").strip()
            r_type = raw_type if raw_type else f"Run cycle {base_cycle_count + i}"
            run_time = request.POST.get(f"new_run_time_{i}")
            end_time = request.POST.get(f"new_end_time_{i}")
            if not run_time and not end_time:
                continue

            import datetime as dt
            rt = (parse_time(run_time) if run_time else None) or dt.time(0, 0)
            et = (parse_time(end_time) if end_time else None) or dt.time(0, 0)

            MachineRunTime.objects.update_or_create(
                service_report=report,
                run_type=r_type,
                defaults={
                    "run_time": rt,
                    "end_time": et,
                    "checked": request.POST.get(f"new_checked_run_{i}") == "on",
                    "pass_status": request.POST.get(f"new_pass_run_{i}") == "on",
                    "fail_status": request.POST.get(f"new_fail_run_{i}") == "on",
                    "remark": request.POST.get(f"new_remark_run_{i}", "").strip(),
                }
            )



from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import (
    ServiceReport, ElectronicItemStatus, PumpStatus, ChemicalItemStatus,
    MiscellaneousItemStatus, ElectronicPanelStatus, WastewaterParameterStatus,
    MachineRunTime, ToolStatus
)

def get_checkbox_states(model, field_name, report):
    result = {}
    for obj in model.objects.filter(report=report):
        key = getattr(obj, field_name).id
        result[str(key)] = {
            "checked": obj.checked,
            "repair": obj.repair,
            "replacement": obj.replacement,
            "remark": obj.remark or ""
        }
    return result

def get_tool_statuses(report):
    tools = {}
    for tool in ToolStatus.objects.filter(service_report=report):
        tools[str(tool.tool.id)] = {
            "quantity": tool.quantity,
            "remark": tool.remark or "",
            "taken_status": tool.taken_status,
        }
    return tools

def get_machine_run_times(report):
    runs = {}
    for idx, run in enumerate(report.run_times.all(), start=1):
        key = f"run_{idx}"
        runs[key] = {
            "run_time": run.run_time.strftime('%H:%M') if run.run_time else "",
            "end_time": run.end_time.strftime('%H:%M') if run.end_time else "",
            "checked": run.checked,
            "pass_status": run.pass_status,
            "fail_status": run.fail_status,
            "remark": run.remark or "",
        }
    return runs

def get_report_draft(request, pk):
    report = get_object_or_404(ServiceReport, pk=pk)

    # ✅ Split and prepare remark_orm_X and spare_X keys
    remark_lines = (report.other_remarks or "").splitlines()
    spare_lines = (report.spares_details or "").splitlines()

    remarks_dict = {
        f"remark_orm_{i+1}": line.strip()
        for i, line in enumerate(remark_lines) if line.strip()
    }
    spares_dict = {
        f"spare_{i+1}": line.strip()
        for i, line in enumerate(spare_lines) if line.strip()
    }


    # ✅ JSON data
    response_data = {
        # Basic Data
        "service_name": report.service_name,
        "customer_name": report.customer_name,
        "phone_no": report.phone_no,
        "location": report.location,
        "reason_of_visit": report.reason_of_visit,
        "contact_number": report.contact_number,
        "date_of_visit": report.date_of_visit.isoformat() if report.date_of_visit else "",
        "in_time": report.in_time.strftime('%H:%M') if report.in_time else "",
        "out_time": report.out_time.strftime('%H:%M') if report.out_time else "",
        "date_of_complaint": report.date_of_complaint.isoformat() if report.date_of_complaint else "",
        "status_of_call": report.status_of_call,
        "service_person_name": report.service_person_name,
        "client_name": report.client_name,
        "client_signed": report.client_signed,
        "zone": report.zone.id if report.zone else "",
        "site": report.site.id if report.site else "",
        "state": report.state.name if report.state else "",

        # Base64 signatures
        "service_person_signature": report.service_person_signature,
        "client_signature": report.client_signature,

        # Checkbox groups
        "electronic_items": get_checkbox_states(ElectronicItemStatus, "item", report),
        "pumps": get_checkbox_states(PumpStatus, "pump", report),
        "chemical_items": get_checkbox_states(ChemicalItemStatus, "item", report),
        "miscellaneous_items": get_checkbox_states(MiscellaneousItemStatus, "item", report),
        "electronic_panels": get_checkbox_states(ElectronicPanelStatus, "panel", report),
        "wastewater_parameters": get_checkbox_states(WastewaterParameterStatus, "parameter", report),

        # Tools & Runtime
        "tool_statuses": get_tool_statuses(report),
        "machine_runs": get_machine_run_times(report),
    }

    # ✅ Inject dynamic remark/spare fields
    response_data.update(remarks_dict)
    print(remarks_dict)
    response_data.update(spares_dict)
    print(spares_dict)


    return JsonResponse(response_data)






from django.views.decorators.http import require_POST
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
import json
@require_POST


@csrf_exempt
@login_required
def reject_service_report(request, pk):
    service_report = get_object_or_404(ServiceReport, pk=pk)
    sr_perms = get_service_report_permissions(request.user)
    if not sr_perms['can_approve_reject']:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'status': 'error', 'message': 'Permission denied. Service Managers or Admins only.'}, status=403)
        return HttpResponseForbidden("Permission denied. Service Managers or Admins only.")
    
    if request.method == 'POST':
        data = json.loads(request.body)
        reason = data.get('reason', '')
        service_report.reject(reason)
        
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({'status': 'success', 'message': 'Report rejected successfully.'})
            
        return redirect('servicereport')
    
    return HttpResponseForbidden("Invalid method.")

@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_sites(request):

    fetch_type = request.GET.get('fetch')
    zone_id = request.GET.get('zone_id')

    if fetch_type == 'states':
        states = State.objects.all().values('id', 'name')
        return JsonResponse(list(states), safe=False)

    if zone_id:
        try:
            sites = Site.objects.filter(zone_id=int(zone_id)).values('id', 'name')
            return JsonResponse(list(sites), safe=False)
        except (ValueError, TypeError):
            return JsonResponse([], safe=False)
    
    # If no zone_id is provided, fetch and return all zones
    zones = Zone.objects.all().values('id', 'name')
    return JsonResponse(list(zones), safe=False)




def view_service_report(request, pk):
    service_report = ServiceReport.objects.get(pk=pk)

    electronic_item_statuses = ElectronicItemStatus.objects.filter(report=service_report)
    panel_statuses = ElectronicPanelStatus.objects.filter(report=service_report)
    chemical_item_statuses = ChemicalItemStatus.objects.filter(report=service_report)
    pump_statuses = PumpStatus.objects.filter(report=service_report)
    miscellaneous_item_statuses = MiscellaneousItemStatus.objects.filter(report=service_report)
    wastewater_parameter_statuses = WastewaterParameterStatus.objects.filter(report=service_report)
    machine_run_times = MachineRunTime.objects.filter(service_report=service_report)
    tool_statuses = ToolStatus.objects.filter(service_report=service_report)
    existing_attachments = ServiceReportAttachment.objects.filter(service_report=service_report)

    context = {
        'service_report': service_report,
        'electronic_item_statuses': electronic_item_statuses,
        'panel_statuses': panel_statuses,
        'chemical_item_statuses': chemical_item_statuses,
        'pump_statuses': pump_statuses,
        'miscellaneous_item_statuses': miscellaneous_item_statuses,
        'wastewater_parameter_statuses': wastewater_parameter_statuses,
        'machine_run_times': machine_run_times,
        'tool_statuses': tool_statuses,
        'existing_attachments': existing_attachments,
        'can_edit_service_reports': can_user_edit_service_report(request.user),
        'sr_perms': get_service_report_permissions(request.user),
        'user_role': get_service_report_permissions(request.user)['role'],
    }    

    return render(request, 'apage/servicereport_detail.html', context)

from django.shortcuts import render, get_object_or_404, redirect
from .models import (
    ServiceReport,
    ElectronicItemStatus,
    ElectronicPanelStatus,
    ChemicalItemStatus,
    PumpStatus,
    MiscellaneousItemStatus,
    WastewaterParameterStatus,
    MachineRunTime,
    ToolStatus,
)
from django.shortcuts import render, get_object_or_404, redirect
from .models import (
    ServiceReport, Zone, Site, State, ServiceReportAttachment,
    ElectronicItem, ElectronicItemStatus,
    ElectronicPanel, ElectronicPanelStatus,
    ChemicalItem, ChemicalItemStatus,
    Pump, PumpStatus,
    MiscellaneousItem, MiscellaneousItemStatus,
    WastewaterParameter, WastewaterParameterStatus,
    MachineRunTime, Tool, ToolStatus
)
@csrf_exempt
def edit_service_report(request, report_id):
    user = get_user_from_request(request)
    if user.is_anonymous:
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION', '')
        is_api = auth_header.startswith('Token ') or request.headers.get('Accept') == 'application/json' or request.content_type == 'application/json'
        if is_api:
            return JsonResponse({"status": "error", "message": "Authentication required."}, status=401)
        return redirect('login')

    if not can_user_edit_service_report(user):
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION', '')
        is_api = auth_header.startswith('Token ') or request.headers.get('Accept') == 'application/json' or request.content_type == 'application/json'
        if is_api:
            return JsonResponse({"status": "error", "message": "You do not have permission to edit service reports."}, status=403)
        messages.error(request, "You do not have permission to edit service reports.")
        return redirect('servicereport')

    service_report = get_object_or_404(ServiceReport, id=report_id)
    if service_report.status == 'approved':
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION', '')
        is_api = auth_header.startswith('Token ') or request.headers.get('Accept') == 'application/json' or request.content_type == 'application/json'
        if is_api:
            return JsonResponse({"status": "error", "message": "Approved service reports cannot be edited."}, status=403)
        messages.error(request, "Approved service reports cannot be edited.")
        return redirect('servicereport')

    service_report.edited_by = user

    existing_attachments = ServiceReportAttachment.objects.filter(service_report=service_report)
    zones = Zone.objects.all()
    sites = Site.objects.filter(zone=service_report.zone) if service_report.zone else []
    states = State.objects.all()

    # ✅ Ensure all item statuses are initialized and always fetched
    electronic_items = [
        safe_get_or_create(ElectronicItemStatus, report=service_report, item=item)[0]
        for item in ElectronicItem.objects.all()
    ]

    electronic_panels = [
        safe_get_or_create(ElectronicPanelStatus, report=service_report, panel=panel)[0]
        for panel in ElectronicPanel.objects.all()
    ]

    chemical_items = [
        safe_get_or_create(ChemicalItemStatus, report=service_report, item=item)[0]
        for item in ChemicalItem.objects.all()
    ]

    pumps = [
        safe_get_or_create(PumpStatus, report=service_report, pump=pump)[0]
        for pump in Pump.objects.all()
    ]

    miscellaneous_items = [
        safe_get_or_create(MiscellaneousItemStatus, report=service_report, item=item)[0]
        for item in MiscellaneousItem.objects.all()
    ]

    wastewater_parameters = [
        safe_get_or_create(WastewaterParameterStatus, report=service_report, parameter=p)[0]
        for p in WastewaterParameter.objects.all()
    ]

    tools = [
        safe_get_or_create(ToolStatus, service_report=service_report, tool=tool)[0]
        for tool in Tool.objects.all()
    ]

    machine_runs = MachineRunTime.objects.filter(service_report=service_report)

    if request.method == 'POST':
        auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION', '')
        is_api = (
            auth_header.startswith('Token ')
            or request.headers.get('Accept') == 'application/json'
            or request.content_type == 'application/json'
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        )

        try:
            # Service Report basic fields
            service_report.service_name = request.POST.get('service_name') or service_report.service_name
            visit_date_val = request.POST.get('date_of_visit')
            parsed_visit_date = parse_date(visit_date_val) if visit_date_val else None
            if parsed_visit_date:
                service_report.date_of_visit = parsed_visit_date

            zone_id = request.POST.get('zone')
            site_id = request.POST.get('site')
            service_report.zone = Zone.objects.filter(id=zone_id).first() if (zone_id and str(zone_id).isdigit()) else None
            service_report.site = Site.objects.filter(id=site_id).first() if (site_id and str(site_id).isdigit()) else None
            service_report.phone_no = request.POST.get('phone_no') or None
            service_report.reason_of_visit = request.POST.get('reason_of_visit') or None
            in_time_val = request.POST.get('in_time')
            service_report.in_time = parse_time(in_time_val) if in_time_val else None
            out_time_val = request.POST.get('out_time')
            service_report.out_time = parse_time(out_time_val) if out_time_val else None
            service_report.customer_name = request.POST.get('customer_name') or None
            service_report.contact_number = request.POST.get('contact_number') or None
            service_report.location = request.POST.get('location') or None
            service_report.status_of_call = request.POST.get('status_of_call') or None
            doc_val = request.POST.get('date_of_complaint')
            service_report.date_of_complaint = parse_date(doc_val) if doc_val else None

            # Signatures & Names
            service_report.service_person_name = request.POST.get('service_person_name') or None
            service_report.client_name = request.POST.get('client_name') or None
            sp_sig = request.POST.get('service_person_signature')
            if is_valid_drawn_signature(sp_sig):
                service_report.service_person_signature = sp_sig
            cl_sig = request.POST.get('client_signature')
            if is_valid_drawn_signature(cl_sig):
                service_report.client_signature = cl_sig
                service_report.client_signed = True

            # Handle State
            state_id = request.POST.get('state')
            if state_id:
                if str(state_id).isdigit():
                    service_report.state = State.objects.filter(id=state_id).first()
                else:
                    service_report.state = State.objects.filter(name=state_id).first()
            else:
                service_report.state = None

            # Handle Remarks
            remarks = [v.strip() for k, v in request.POST.items() if k.startswith('remark_orm_') and v.strip()]
            spares = [v.strip() for k, v in request.POST.items() if k.startswith('spare_') and v.strip()]
            service_report.other_remarks = '\n'.join(remarks)
            service_report.spares_details = '\n'.join(spares)

            # Handle Attachments
            to_remove = request.POST.getlist('remove_attachment')
            if to_remove:
                ServiceReportAttachment.objects.filter(id__in=to_remove).delete()

            for f in request.FILES.getlist('new_attachment'):
                ServiceReportAttachment.objects.create(service_report=service_report, file=f)

            # Helper to update dynamic items
            def update_status(obj, prefix, base_attr):
                base_id = getattr(obj, base_attr).id
                obj.checked = f'checked_{prefix}{base_id}' in request.POST
                obj.repair = f'repair_{prefix}{base_id}' in request.POST
                obj.replacement = f'replacement_{prefix}{base_id}' in request.POST
                obj.remark = request.POST.get(f'remark_{prefix}{base_id}', '')
                obj.save()

            # Update all item statuses (keep correct prefixes)
            for item in electronic_items:
                update_status(item, 'eitems_', 'item')

            for panel in electronic_panels:
                update_status(panel, 'epanels_', 'panel')

            for item in chemical_items:
                update_status(item, 'chemical_', 'item')

            for pump in pumps:
                update_status(pump, 'pump_', 'pump')

            for item in miscellaneous_items:
                update_status(item, 'miscellaneous_', 'item')

            for param in wastewater_parameters:
                update_status(param, 'wastewater_', 'parameter')

            # Machine run times
            for run in machine_runs:
                raw_rt = request.POST.get(f'run_time_{run.id}')
                raw_et = request.POST.get(f'end_time_{run.id}')
                if raw_rt:
                    parsed_rt = parse_time(raw_rt)
                    if parsed_rt:
                        run.run_time = parsed_rt
                if raw_et:
                    parsed_et = parse_time(raw_et)
                    if parsed_et:
                        run.end_time = parsed_et
                run.checked = f'checked_run_{run.id}' in request.POST
                run.pass_status = f'pass_run_{run.id}' in request.POST
                run.fail_status = f'fail_run_{run.id}' in request.POST
                run.remark = request.POST.get(f'remark_run_{run.id}', '')
                run.save()

            # Tools
            for tool in tools:
                base_id = tool.tool.id
                qty = request.POST.get(f'quantity_{base_id}', '')
                tool.quantity = int(qty) if qty.isdigit() else 0
                tool.remark = request.POST.get(f'remark_tools_{base_id}', '')
                tool.taken_status = f'taken_status_{base_id}' in request.POST
                tool.save()

            # Handle New Machine Run Times
            try:
                new_run_count = int(request.POST.get('new_machine_run_count', 0))
            except ValueError:
                new_run_count = 0

            base_cycle_count = int(request.POST.get('run_cycle_count', 0))
            import datetime as dt
            for i in range(1, new_run_count + 1):
                raw_type = request.POST.get(f'new_run_type_{i}', '').strip()
                r_type = raw_type if raw_type else f"Run cycle {base_cycle_count + i}"
                raw_nrt = request.POST.get(f'new_run_time_{i}')
                raw_net = request.POST.get(f'new_end_time_{i}')
                if not raw_nrt and not raw_net:
                    continue
                rt = (parse_time(raw_nrt) if raw_nrt else None) or dt.time(0, 0)
                et = (parse_time(raw_net) if raw_net else None) or dt.time(0, 0)
                MachineRunTime.objects.update_or_create(
                    service_report=service_report,
                    run_type=r_type,
                    defaults={
                        'run_time': rt,
                        'end_time': et,
                        'checked': f'new_checked_run_{i}' in request.POST,
                        'pass_status': f'new_pass_run_{i}' in request.POST,
                        'fail_status': f'new_fail_run_{i}' in request.POST,
                        'remark': request.POST.get(f'new_remark_run_{i}', '').strip(),
                    }
                )

            # Reset status if it was rejected/draft so it can be reviewed again
            if service_report.status == 'rejected' or service_report.is_draft:
                service_report.status = 'pending'
                service_report.rejection_reason = None
            service_report.is_draft = False
            service_report.save()

            from django.urls import reverse
            if is_api:
                attachments = []
                for a in ServiceReportAttachment.objects.filter(service_report=service_report):
                    attachments.append({
                        'id': a.id,
                        'file_url': a.file.url if a.file else '',
                        'name': a.file.name if a.file else ''
                    })
                return JsonResponse({
                    "status": "success",
                    "report_id": service_report.id,
                    "redirect_url": reverse('servicereport'),
                    "attachments": attachments
                })

            return redirect('servicereport')

        except Exception as e:
            import traceback
            traceback.print_exc()
            if is_api:
                return JsonResponse({"status": "error", "message": str(e)}, status=500)
            from django.contrib import messages
            messages.error(request, f"Error saving report: {e}")
            return redirect('service_report_edit', report_id=service_report.id)

    return render(request, 'apage/edit_service_report.html', {
        'service_report': service_report,
        'electronic_items': electronic_items,
        'electronic_panels': electronic_panels,
        'chemical_items': chemical_items,
        'pumps': pumps,
        'miscellaneous_items': miscellaneous_items,
        'wastewater_parameters': wastewater_parameters,
        'tools': tools,
        'machine_runs': machine_runs,
        'states': states,
        'zones': zones,
        'sites': sites,
        'existing_attachments': existing_attachments,
    })

from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponse
# from weasyprint import HTML
from .models import (
    ServiceReport,
    ElectronicItemStatus,
    ElectronicPanelStatus,
    ChemicalItemStatus,
    PumpStatus,
    MiscellaneousItemStatus,
    WastewaterParameterStatus,
    MachineRunTime,
    ToolStatus,
    State,
)

from apage.models import ServiceReportAttachment  # adjust import if needed
from django.conf import settings
from urllib.parse import urljoin
import os

def service_report_pdf(request, pk):
    print("GOT IN")
    service_report = ServiceReport.objects.get(pk=pk)
    electronic_item_statuses = ElectronicItemStatus.objects.filter(report=service_report)
    panel_statuses = ElectronicPanelStatus.objects.filter(report=service_report)
    chemical_item_statuses = ChemicalItemStatus.objects.filter(report=service_report)
    pump_statuses = PumpStatus.objects.filter(report=service_report)
    miscellaneous_item_statuses = MiscellaneousItemStatus.objects.filter(report=service_report)
    wastewater_parameter_statuses = WastewaterParameterStatus.objects.filter(report=service_report)
    machine_run_times = MachineRunTime.objects.filter(service_report=service_report)
    tool_statuses = ToolStatus.objects.filter(service_report=service_report)
    import base64
    attachments = ServiceReportAttachment.objects.filter(service_report=service_report)

    from PIL import Image
    import io
    
    for attachment in attachments:
        try:
            if os.path.exists(attachment.file.path):
                ext = attachment.file.path.split('.')[-1].lower()
                mime_type = "image/png" if ext == "png" else "image/jpeg"
                
                # Compress image using Pillow to prevent Weasyprint Out-Of-Memory (OOM) crash
                with Image.open(attachment.file.path) as img:
                    # Convert to RGB if it's RGBA and saving as JPEG
                    if img.mode in ('RGBA', 'P') and mime_type == 'image/jpeg':
                        img = img.convert('RGB')
                        
                    img.thumbnail((800, 800)) # Resize to max 800x800
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG" if ext == "png" else "JPEG", quality=75)
                    b64_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    
                attachment.local_url = f"data:{mime_type};base64,{b64_data}"
            else:
                attachment.local_url = ""
        except Exception as e:
            print(f"Error processing attachment {attachment.id}: {e}")
            attachment.local_url = ""

    context = {
        'service_report': service_report,
        'electronic_item_statuses': electronic_item_statuses,
        'panel_statuses': panel_statuses,
        'chemical_item_statuses': chemical_item_statuses,
        'pump_statuses': pump_statuses,
        'miscellaneous_item_statuses': miscellaneous_item_statuses,
        'wastewater_parameter_statuses': wastewater_parameter_statuses,
        'machine_run_times': machine_run_times,
        'tool_statuses': tool_statuses,
        'attachments': attachments,
    }

    html_string = render_to_string('apage/pdf_servicereport.html', context)

    from weasyprint import HTML
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    
    # Pass the pdf bytes directly into the constructor to automatically set Content-Length
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="service_report_{pk}.pdf"'

    return response



from django.shortcuts import render
from .models import ServiceReport, ServiceReportEditLog, ElectronicItemStatus, ElectronicPanelStatus, ChemicalItemStatus, PumpStatus, MiscellaneousItemStatus, WastewaterParameterStatus, MachineRunTime, ToolStatus

def servireport_edithistory(request, report_id):
    # Get the specific ServiceReport
    service_report = ServiceReport.objects.get(id=report_id)

    # Get the edit logs for this report
    edit_logs = ServiceReportEditLog.objects.filter(report=service_report).order_by('-edit_timestamp')
    service_report.user = request.user

    # Get the related statuses and data for the report
    electronic_item_statuses = ElectronicItemStatus.objects.filter(report=service_report)
    panel_statuses = ElectronicPanelStatus.objects.filter(report=service_report)
    chemical_item_statuses = ChemicalItemStatus.objects.filter(report=service_report)
    pump_statuses = PumpStatus.objects.filter(report=service_report)
    miscellaneous_item_statuses = MiscellaneousItemStatus.objects.filter(report=service_report)
    wastewater_parameter_statuses = WastewaterParameterStatus.objects.filter(report=service_report)
    machine_run_times = MachineRunTime.objects.filter(service_report=service_report)
    tool_statuses = ToolStatus.objects.filter(service_report=service_report)

    # Pass all the necessary data to the template
    context = {
        'service_report': service_report,
        'edit_logs': edit_logs,
        'electronic_item_statuses': electronic_item_statuses,
        'panel_statuses': panel_statuses,
        'chemical_item_statuses': chemical_item_statuses,
        'pump_statuses': pump_statuses,
        'miscellaneous_item_statuses': miscellaneous_item_statuses,
        'wastewater_parameter_statuses': wastewater_parameter_statuses,
        'machine_run_times': machine_run_times,
        'tool_statuses': tool_statuses,
    }

    return render(request, 'apage/edithistory_servicereport.html', context)

@csrf_exempt
@api_view(['GET', 'POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def update_service_report_status(request, pk, action):
    service_report = get_object_or_404(ServiceReport, pk=pk)
    
    # Ensure only managers or admins can approve/reject
    user = request.user
    sr_perms = get_service_report_permissions(user)
    if not sr_perms['can_approve_reject']:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({"status": "error", "message": "Permission denied. Service Managers or Admins only."}, status=403)
        return HttpResponseForbidden("Permission denied. Service Managers or Admins only.")

    if action == 'approve':
        service_report.approve()
        
        # If it's an API request (POST or JSON), return JSON
        if request.method == 'POST' or request.content_type == 'application/json':
            return JsonResponse({"status": "success", "message": "Report approved successfully."})
        
        # If it's a regular web browser GET request, redirect back
        messages.success(request, "Report approved successfully.")
        return redirect('servicereport')
    elif action == 'reject':
        # Try to get reason from JSON body or POST data
        try:
            data = json.loads(request.body)
            reason = data.get('reason', '')
        except:
            reason = request.POST.get('reason', '')

        if not reason:
            return JsonResponse({"status": "error", "message": "Rejection reason is required."}, status=400)

        service_report.reject(reason)
        return JsonResponse({"status": "success", "message": "Report rejected successfully."})
    else:
        return JsonResponse({"status": "error", "message": "Invalid action."}, status=400)


from django.shortcuts import render, get_object_or_404, redirect
from .models import ServiceReport
from .forms import ClientSignatureForm  # we'll create this

def client_sign_report(request, pk):
    report = get_object_or_404(ServiceReport, pk=pk)

    if request.method == 'POST':
        form = ClientSignatureForm(request.POST)
        if form.is_valid():
            report.client_name = form.cleaned_data['client_name']
            report.client_signature = form.cleaned_data['client_signature']  # base64
            report.save()
            return render(request, 'apage/client_signature_success.html', {'report': report})
    else:
        form = ClientSignatureForm()

    return render(request, 'apage/client_sign_report.html', {
        'report': report,
        'form': form,
    })

from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from .models import (
    ServiceReport, ElectronicItemStatus, ElectronicPanelStatus, ChemicalItemStatus,
    PumpStatus, MiscellaneousItemStatus, WastewaterParameterStatus,
    MachineRunTime, ToolStatus, ServiceReportAttachment
)

from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from apage.models import (
    ServiceReport, ElectronicItemStatus, ElectronicPanelStatus,
    ChemicalItemStatus, PumpStatus, MiscellaneousItemStatus,
    WastewaterParameterStatus, MachineRunTime, ToolStatus,
    ServiceReportAttachment
)

@csrf_exempt
def client_sign_view(request, pk):
    print("GOT HITTING")
    report = get_object_or_404(ServiceReport, pk=pk)

    # ✅ Prevent access if already signed
    if report.client_signed:
        return render(request, "apage/link_expired.html", {"report": report})

    # Fetch related status models
    electronic_item_statuses = ElectronicItemStatus.objects.filter(report=report)
    panel_statuses = ElectronicPanelStatus.objects.filter(report=report)
    chemical_item_statuses = ChemicalItemStatus.objects.filter(report=report)
    pump_statuses = PumpStatus.objects.filter(report=report)
    miscellaneous_item_statuses = MiscellaneousItemStatus.objects.filter(report=report)
    wastewater_parameter_statuses = WastewaterParameterStatus.objects.filter(report=report)
    machine_run_times = MachineRunTime.objects.filter(service_report=report)
    tool_statuses = ToolStatus.objects.filter(service_report=report)
    attachments = ServiceReportAttachment.objects.filter(service_report=report)

    error = None

    if request.method == "POST":
        print("GOY ING TO SIGN")
        name = (request.POST.get("client_name") or "").strip()
        signature = (request.POST.get("client_signature") or "").strip()
        remark = (request.POST.get("client_remark") or "").strip()

        print("POST client_name:", name)
        print("POST client_signature starts with:", signature[:30] if signature else "None")
        print("Received POST:", name[:50], signature[:50] if signature else "No Signature")

        if not name or name.lower() == 'none':
            error = "Please enter your name."
        elif not is_valid_drawn_signature(signature):
            error = "You haven't signed yet! Please draw your signature in the signature box before submitting."
        else:
            report.client_name = name
            report.client_signature = signature
            report.client_remark = remark 
            report.client_signed = True  # ✅ Set flag to prevent reuse
            report.save()
            return render(request, "apage/sign_success.html", {"report": report})

    context = {
        "service_report": report,
        "electronic_item_statuses": electronic_item_statuses,
        "panel_statuses": panel_statuses,
        "chemical_item_statuses": chemical_item_statuses,
        "pump_statuses": pump_statuses,
        "miscellaneous_item_statuses": miscellaneous_item_statuses,
        "wastewater_parameter_statuses": wastewater_parameter_statuses,
        "machine_run_times": machine_run_times,
        "tool_statuses": tool_statuses,
        "attachments": attachments,
        "error": error,
    }

    return render(request, "apage/client_sign.html", context)
# ---------------------------------dashboard----------------------

from django.shortcuts import render
from django.db.models import Count
from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum
from django.contrib.auth.models import User

from .models import ServiceReport, MOM, MaintenanceChecklist, GeneralReport

def dashboard(request):
    today = timezone.now().date()
    user = request.user
    user_role = user.groups.first().name if user.groups.exists() else None
    if user.is_superuser or user.is_staff:
        user_role = 'Admin'
    print("user role",user_role)
    # Default to current month
    start_date = today.replace(day=1)

    users = User.objects.all()
    sites = Site.objects.all()
    print("sites",sites)
    print(sites.count())

    # Get the selected time range from the query parameters (defaults to 'month')
    time_range = request.GET.get('time_range', 'month')

    if time_range == 'week':
        # Start date for the last week (7 days ago)
        start_date = today - timedelta(days=7)
    elif time_range == 'month':
        # Start date for the current month (1st day of this month)
        start_date = today.replace(day=1)
    elif time_range == '60_days':
        # Start date for the last 60 days
        start_date = today - timedelta(days=60)
    elif time_range == '3_months':
        # Start date for the last 3 months (approx. 90 days)
        start_date = today - timedelta(days=90)
    elif time_range == '6_months':
        # Start date for the last 6 months (approx. 180 days)
        start_date = today - timedelta(days=180)
    elif time_range == '1_year':
        # Start date for the last 1 year (approx. 365 days)
        start_date = today - timedelta(days=365)

    # Aggregates for selected time range
    # Check user role and filter reports
    user = request.user
    print(user)
    user_role = user.groups.first().name if user.groups.exists() else None
    if user.is_superuser or user.is_staff:
        user_role = 'Admin'
    completeion = request.GET.get('status', 'all')
    # New Filters
    created_by = request.GET.get('created_by')
    print("created by",created_by)
    selected_site = request.GET.get('site')


    if user_role == "Admin":
        # Admin users can see all reports
        service_reports = ServiceReport.objects.filter(created_date__gte=start_date)
        mom_reports = MOM.objects.filter(created_date__gte=start_date)
        maintenance_reports = MaintenanceChecklist.objects.filter(date__gte=start_date)
        general_reports = GeneralReport.objects.filter(created_date__gte=start_date)
    else:
        # Non-admin users can only see their reports
        service_reports = ServiceReport.objects.filter(created_by=request.user, created_date__gte=start_date)
        mom_reports = MOM.objects.filter(created_by=request.user, created_date__gte=start_date)
        maintenance_reports = MaintenanceChecklist.objects.filter(created_by=request.user, date__gte=start_date)
        general_reports = GeneralReport.objects.filter(created_by=request.user, created_date__gte=start_date)

     # Apply status filter
    if completeion != 'all':
        service_reports = service_reports.filter(status=completeion)
        maintenance_reports = maintenance_reports.filter(status=completeion)

    # Apply created_by filter
    if created_by:
        service_reports = service_reports.filter(created_by_id=created_by)

    # Apply site filter
    if selected_site:
        service_reports = service_reports.filter(site_id=selected_site)

    months_in_range = ((today.year - start_date.year) * 12 + today.month - start_date.month) + 1
    required_service_reports = 2 * months_in_range
    required_maintenance_checklists = 4 * months_in_range

    if  created_by and  not selected_site:
        required_service_reports = 2 * sites.count() * months_in_range
        print("required_service_reports",required_service_reports)

    total_service_reports = service_reports.count()
    total_maintenance_reports = maintenance_reports.count()

    service_compliance = min(total_service_reports / required_service_reports, 1) *100
    if total_maintenance_reports > required_maintenance_checklists:
        maintenance_compliance = max(total_maintenance_reports / required_maintenance_checklists, 1) *100
    else :
        maintenance_compliance =min(total_maintenance_reports / required_maintenance_checklists, 1) *100
    service_submitted = total_service_reports
    service_remaining = max(0, required_service_reports - total_service_reports)

    maintenance_submitted = total_maintenance_reports
    maintenance_remaining = max(0, required_maintenance_checklists - total_maintenance_reports)

    compliance_status = {
        'service': {
            'compliance': service_compliance,
            'status': "green" if service_compliance == 100 else ("yellow" if service_compliance < 100 else "blue"),
        },
        'maintenance': {
            'compliance': maintenance_compliance,
            'status': "blue" if maintenance_compliance > 100 else ("yellow" if maintenance_compliance < 100 else "green"),
        }
    }
    print(compliance_status)
    print(completeion)

    # Total count for each report type for selected time range
    total_service_reports = service_reports.count()
    total_mom_reports = mom_reports.count()
    total_maintenance_reports = maintenance_reports.count()
    total_general_reports = general_reports.count()

    # Context to pass to the template
    context = {
        'service_reports': service_reports,
        'mom_reports': mom_reports,
        'maintenance_reports': maintenance_reports,
        'general_reports': general_reports,
        'total_service_reports': total_service_reports,
        'total_mom_reports': total_mom_reports,
        'total_maintenance_reports': total_maintenance_reports,
        'total_general_reports': total_general_reports,
        'time_range': time_range,
        'compliance_status': compliance_status,
        'service_submitted': service_submitted,
        'service_remaining': service_remaining,
        'maintenance_submitted': maintenance_submitted,
        'maintenance_remaining': maintenance_remaining,
        'status_filter':completeion,
        'created_by': created_by,
        'selected_site': selected_site,
        'users': users,
        'sites': sites,
    }
    return render(request, 'apage/dashboard.html', context)


# --------------------------------------------------Generator Report---------------------------------------

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from datetime import datetime, timedelta   # ✅ THIS WAS MISSING

from .models import GeneratorReport


@login_required
def add_generator_report(request):
    if request.method == "POST":
        date = request.POST.get("date")
        start_time = request.POST.get("start_time")

        try:
            # Convert values
            date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            start_time_obj = datetime.strptime(start_time, "%H:%M").time()

            # Ensure last entry has an end_time before allowing a new entry
            last_entry = GeneratorReport.objects.filter(
                created_by=request.user
            ).order_by('-id').first()

            if last_entry and last_entry.end_time is None:
                return JsonResponse(
                    {"error": "Cannot add a new entry while the last entry is incomplete."},
                    status=400
                )

            # Save to DB
            print("start :", start_time_obj)
            print("start :", start_time)

            GeneratorReport.objects.create(
                created_by=request.user,
                date=date_obj,
                start_time=start_time_obj,
            )

            return redirect('generator_report')

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return render(request, "apage/add_generator_report.html")


import datetime as dt
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import GeneratorReport


@login_required
def edit_generator_report(request, report_id):
    report = get_object_or_404(GeneratorReport, id=report_id, created_by=request.user)

    if request.method == "POST":
        end_time = request.POST.get("end_time")

        try:
            end_time_obj = dt.datetime.strptime(end_time, "%H:%M").time()

            start_datetime = dt.datetime.combine(report.date, report.start_time)
            end_datetime = dt.datetime.combine(report.date, end_time_obj)

            if end_datetime < start_datetime:
                end_datetime += dt.timedelta(days=1)

            total_time_obj = end_datetime - start_datetime

            report.end_time = end_time_obj
            report.total_time = total_time_obj
            report.save()

            return redirect('generator_report')

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return render(request, "apage/edit_generator_report.html", {"report": report})


@login_required
def generator_report(request):
    user = request.user
    user_role = user.groups.first().name if user.groups.first() else None
    if user.is_superuser or user.is_staff:
        user_role = 'Admin'
    
    if user_role == 'Admin' or user.is_staff or user.is_superuser:
        reports = GeneratorReport.objects.all().order_by('-date')
    else:
        reports = GeneratorReport.objects.filter(
            created_by=user
        ).order_by('-date')

    return render(
        request,
        'apage/GeneratorReports_viewing.html',
        {'reports': reports}
    )


from django.http import HttpResponseForbidden
from django.contrib import messages
from .models import SiteAMC, Site, SiteAMCWaterReport

@login_required
def site_amc_management(request):
    sites = Site.objects.all().order_by('name')
    for site in sites:
        SiteAMC.objects.get_or_create(site=site)
    amcs = SiteAMC.objects.select_related('site').prefetch_related('water_reports').all().order_by('site__name')
    
    if request.method == 'POST':
        has_profile = hasattr(request.user, 'userprofile')
        is_xpredict = has_profile and request.user.userprofile.is_xpredict
        if not (request.user.is_staff or request.user.is_superuser or is_xpredict):
             return HttpResponseForbidden("You do not have permission to manage AMCs.")
             
        site_id = request.POST.get('site_id')
        has_amc = request.POST.get('has_amc') == 'on'
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        proof_file = request.FILES.get('proof_file')
        
        site = get_object_or_404(Site, id=site_id)
        
        amc, created = SiteAMC.objects.get_or_create(site=site)
        
        # Save old details to history before updating if it already existed
        if not created and amc.has_amc:
            from apage.models import SiteAMCHistory
            SiteAMCHistory.objects.create(
                amc=amc,
                amc_start_date=amc.amc_start_date,
                amc_end_date=amc.amc_end_date,
                proof_file=amc.proof_file if amc.proof_file else None
            )
            
        amc.has_amc = has_amc
        if has_amc:
            amc.amc_start_date = start_date if start_date else None
            amc.amc_end_date = end_date if end_date else None
            if proof_file:
                amc.proof_file = proof_file
        else:
            amc.amc_start_date = None
            amc.amc_end_date = None

        amc.save()
        messages.success(request, f"AMC details updated successfully for {site.name}.")
        return redirect('site_amc_management')

    from datetime import date
    return render(request, 'apage/site_amc.html', {
        'sites': sites,
        'amcs': amcs,
        'today': date.today(),
        'current_year': date.today().year,
    })


@login_required
def upload_site_amc_water_reports(request, amc_id):
    has_profile = hasattr(request.user, 'userprofile')
    is_xpredict = has_profile and request.user.userprofile.is_xpredict
    if not (request.user.is_staff or request.user.is_superuser or is_xpredict):
        return HttpResponseForbidden("You do not have permission to manage AMCs.")

    amc = get_object_or_404(SiteAMC, id=amc_id)
    if request.method == 'POST':
        files = request.FILES.getlist('water_reports')
        report_date_str = request.POST.get('report_date')
        if not files:
            messages.warning(request, "No files were selected for upload.")
            return redirect('site_amc_management')

        for f in files:
            kwargs = {
                'amc': amc,
                'file': f,
                'uploaded_by': request.user if request.user.is_authenticated else None
            }
            if report_date_str:
                kwargs['report_date'] = report_date_str
            SiteAMCWaterReport.objects.create(**kwargs)
        messages.success(request, f"Successfully uploaded {len(files)} water report(s) for {amc.site.name}.")

    return redirect('site_amc_management')


@login_required
def delete_site_amc_water_report(request, report_id):
    has_profile = hasattr(request.user, 'userprofile')
    is_xpredict = has_profile and request.user.userprofile.is_xpredict
    if not (request.user.is_staff or request.user.is_superuser or is_xpredict):
        return HttpResponseForbidden("You do not have permission to manage AMCs.")

    report = get_object_or_404(SiteAMCWaterReport, id=report_id)
    site_name = report.amc.site.name
    filename = report.filename
    if report.file:
        report.file.delete(save=False)
    report.delete()
    messages.success(request, f"Water report '{filename}' deleted successfully for {site_name}.")
    return redirect('site_amc_management')


from .models import Bike, BikeMaintenance
from .forms import BikeMaintenanceForm
from website.models import Notification

@login_required
def bike_maintenance_viewing(request):
    maintenances = BikeMaintenance.objects.all().order_by('-date')
    return render(request, 'apage/bike_maintenance_viewing.html', {'maintenances': maintenances})

@login_required
def bike_maintenance_create(request):
    from .models import BikeMaintenancePhoto
    if request.method == 'POST':
        form = BikeMaintenanceForm(request.POST, request.FILES)
        if form.is_valid():
            maintenance = form.save(commit=False)
            maintenance.reported_by = request.user
            maintenance.save()
            form.save_m2m() # Save tagged users
            
            # Save uploaded photos
            photos = request.FILES.getlist('photos')
            for photo in photos:
                BikeMaintenancePhoto.objects.create(maintenance=maintenance, image=photo)
            
            # Create notifications for tagged users
            tagged_users = form.cleaned_data.get('tagged_users')
            if tagged_users:
                bike_reg = maintenance.bike.registration_number
                for user in tagged_users:
                    if user != request.user: # Don't notify the reporter themselves
                        Notification.objects.create(
                            user=user,
                            title=f"Tagged in Bike Maintenance Issue",
                            message=f"{request.user.username} tagged you in a maintenance report for bike {bike_reg}. Issues: {maintenance.issues_faced}"
                        )
                        
            return redirect('bike_maintenance_viewing')
    else:
        form = BikeMaintenanceForm()
        
    import json
    latest_data = {}
    for bike in Bike.objects.all():
        last_m = bike.maintenances.order_by('-date').first()
        if last_m:
            latest_data[bike.id] = {
                'last_oil_change_or_service_date': last_m.date.strftime('%Y-%m-%d') if last_m.date else '',
                'last_oil_change_km': last_m.current_mileage
            }
        else:
            latest_data[bike.id] = {'last_oil_change_or_service_date': '', 'last_oil_change_km': ''}
            
    return render(request, 'apage/bike_maintenance.html', {
        'form': form, 
        'latest_data_json': json.dumps(latest_data)
    })


@login_required
def service_expiry_management(request):
    from .models import Service, ServiceExpiry
    from datetime import datetime
    services = Service.objects.all().order_by('name')
    expiries = ServiceExpiry.objects.select_related('service').all().order_by('expiry_date')
    
    edit_obj = None
    edit_id = request.GET.get('edit')
    if edit_id:
        edit_obj = get_object_or_404(ServiceExpiry, id=edit_id)

    if request.method == 'POST':
        service_name = request.POST.get('service_name')
        expiry_date_str = request.POST.get('expiry_date')
        email = request.POST.get('email')
        expiry_id = request.POST.get('expiry_id') # For editing

        if not service_name or not expiry_date_str or not email:
            messages.error(request, "All fields are required.")
            return redirect('service_expiry_management')

        service, created = Service.objects.get_or_create(name=service_name.strip())
        
        try:
            expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect('service_expiry_management')

        if expiry_id:
            expiry = get_object_or_404(ServiceExpiry, id=expiry_id)
            expiry.service = service
            expiry.expiry_date = expiry_date
            expiry.email = email.strip()
            expiry.notified = False  # Reset notification status on edit
            expiry.save()
            messages.success(request, "Service expiry updated successfully!")
        else:
            ServiceExpiry.objects.create(
                service=service,
                expiry_date=expiry_date,
                email=email.strip(),
                notified=False
            )
            messages.success(request, "Service expiry added successfully!")

        return redirect('service_expiry_management')

    return render(request, 'apage/service_expiry.html', {
        'services': services,
        'expiries': expiries,
        'edit_obj': edit_obj,
    })


@login_required
def delete_service_expiry(request, expiry_id):
    from .models import ServiceExpiry
    expiry = get_object_or_404(ServiceExpiry, id=expiry_id)
    expiry.delete()
    messages.success(request, "Service expiry deleted successfully!")
    return redirect('service_expiry_management')

import zipfile
import io

@login_required
def bulk_download_service_reports(request):
    user = request.user
    user_role = user.groups.first().name if user.groups.first() else None
    if user.is_superuser or user.is_staff:
        user_role = 'Admin'

    # Base queryset
    if user_role == 'Admin':
        service_reports = ServiceReport.objects.all()
    else:
        service_reports = ServiceReport.objects.filter(created_by=user)
        
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')
    
    if start_date:
        service_reports = service_reports.filter(date_of_visit__gte=start_date)
    if end_date:
        service_reports = service_reports.filter(date_of_visit__lte=end_date)

    search_query = request.GET.get('search', '')
    if search_query:
        from django.db.models import Q
        service_reports = service_reports.filter(
            Q(service_name__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(state__name__icontains=search_query) |
            Q(status_of_call__icontains=search_query) |
            Q(site__name__icontains=search_query)
        )

    user_filter = request.GET.get('user', '')
    if user_filter and user_role == 'Admin':
        service_reports = service_reports.filter(created_by__id=user_filter)

    site_filter = request.GET.get('site', '')
    if site_filter:
        service_reports = service_reports.filter(site__id=site_filter)

    service_reports = service_reports.order_by('-date_of_visit')

    # Generate Zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for report in service_reports:
            try:
                # Reuse the existing PDF generation logic
                pdf_response = service_report_pdf(request, report.id)
                pdf_bytes = pdf_response.content
                
                cust_name = report.customer_name if report.customer_name else "Unknown"
                visit_date = report.date_of_visit if report.date_of_visit else "NoDate"
                filename = f"ServiceReport_{cust_name}_{visit_date}_{report.id}.pdf".replace(" ", "_").replace("/", "-")
                
                zip_file.writestr(filename, pdf_bytes)
            except Exception as e:
                print(f"Error generating PDF for report {report.id}: {e}")
                
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="Bulk_Service_Reports.zip"'
    return response
