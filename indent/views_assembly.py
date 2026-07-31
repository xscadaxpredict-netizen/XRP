from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.urls import reverse
from .models import Project, Department, InternalIndent, GRNItem

@login_required
def project_assembly(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    departments = Department.objects.all()
    
    nodes = []
    
    for dept in departments:
        indent = InternalIndent.objects.filter(project=project, department=dept).first()
        prog = 0
        has_tasks = False
        
        if indent:
            has_tasks = True
            # For simplicity, calculate requested vs accepted
            total_requested = 0
            for item in indent.items.all():
                total_requested += item.quantity
                
            # Accepted quantity
            grn_items = GRNItem.objects.filter(
                grn__internal_indent=indent
            ).values("internal_indent_item_id").annotate(total=models.Sum("accepted_qty"))
            
            total_accepted = sum([g["total"] for g in grn_items if g["total"]])
            
            if total_requested > 0:
                prog = round((total_accepted / total_requested) * 100, 1)
            else:
                prog = 100
                
        # Include department if it has tags or if it's the lead department
        is_lead = (project.lead and dept.id == project.lead.id)
        if has_tasks or is_lead:
            nodes.append({
                "id": dept.id,
                "name": dept.name,
                "progress": min(prog, 100),
                "is_lead": is_lead
            })
    is_deployed = hasattr(project, 'deployment')
            
    return render(request, "indent/project_assembly.html", {
        "project": project,
        "nodes": nodes,
        "is_deployed": is_deployed,
    })

from .models import Deployment, DeploymentImage, DeploymentDocument
from .forms import DeploymentImageForm

@login_required
def project_deploy(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    if request.method == "POST":
        # Check if deployment already exists
        deployment, created = Deployment.objects.get_or_create(project=project)
        
        # Only capture snapshot once when first deployed
        if created or not deployment.department_status_snapshot:
            snapshot_data = []
            departments = Department.objects.all()
            for dept in departments:
                indent = InternalIndent.objects.filter(project=project, department=dept).first()
                if indent:
                    items_data = []
                    dept_requested = 0
                    dept_accepted = 0
                    print(f"Deploy loop dept: {dept.name}, indent: {indent}")
                    for item in indent.items.all():
                        requested = item.quantity
                        dept_requested += requested
                        
                        accepted = sum([g["total"] for g in GRNItem.objects.filter(internal_indent_item=item).values("internal_indent_item_id").annotate(total=models.Sum("accepted_qty")) if g["total"]])
                        dept_accepted += accepted
                        
                        items_data.append({
                            "item_name": item.item_name,
                            "requested": requested,
                            "accepted": accepted,
                            "requested_by": item.requested_by_dept.name if item.requested_by_dept else "Unknown"
                        })
                    
                    prog = round((dept_accepted / dept_requested) * 100, 1) if dept_requested > 0 else 100
                    
                    snapshot_data.append({
                        "id": dept.id,
                        "name": dept.name,
                        "progress": min(prog, 100),
                        "items": items_data
                    })
                elif project.lead and dept == project.lead:
                     snapshot_data.append({
                        "id": dept.id,
                        "name": dept.name,
                        "progress": 0, # Depending on how you calculate lead progress
                        "items": []
                    })
            
            deployment.department_status_snapshot = snapshot_data
            deployment.save()

        # We DO NOT mark project as 'completed' here anymore, as deployment is an ongoing process now
        messages.success(request, "Project pushed to deployment phase. Please fill out loading and document details.")
        return redirect("deployment_details", deployment_id=deployment.id)
    
    return redirect("project_detail", pk=project.id)

@login_required
def deployment_details(request, deployment_id):
    deployment = get_object_or_404(Deployment, pk=deployment_id)
    project = deployment.project
    
    image_form = DeploymentImageForm()
    
    if request.method == "POST":
        if 'upload_images' in request.POST:
            files = request.FILES.getlist('image')
            if files:
                for f in files:
                    DeploymentImage.objects.create(deployment=deployment, image=f)
                messages.success(request, f"{len(files)} image(s) uploaded successfully.")
            else:
                messages.error(request, "Please select at least one image file.")
            return redirect(f"{reverse('deployment_details', args=[deployment.id])}#loading")
            
        elif 'upload_document' in request.POST:
            doc_type = request.POST.get('document_type')
            files = request.FILES.getlist('files')
            if doc_type and files:
                for f in files:
                    DeploymentDocument.objects.create(deployment=deployment, document_type=doc_type, file=f)
                messages.success(request, f"{len(files)} document(s) uploaded for {doc_type.replace('_', ' ').title()}.")
            else:
                messages.error(request, "Please provide a valid document and type.")
            return redirect(f"{reverse('deployment_details', args=[deployment.id])}#docs")
            
        elif 'delete_document' in request.POST:
            doc_id = request.POST.get('doc_id')
            doc = get_object_or_404(DeploymentDocument, pk=doc_id, deployment=deployment)
            doc_type = doc.get_document_type_display()
            doc.delete()
            messages.success(request, f"Deleted {doc_type} successfully.")
            return redirect(f"{reverse('deployment_details', args=[deployment.id])}#docs")
        
    documents_grouped = {}
    for choice in DeploymentDocument.DOCUMENT_TYPES:
        doc_key = choice[0]
        doc_name = choice[1]
        documents_grouped[doc_name] = {
            'key': doc_key,
            'files': deployment.documents.filter(document_type=doc_key).order_by('-uploaded_at')
        }
        
    context = {
        'deployment': deployment,
        'project': project,
        'image_form': image_form,
        'documents_grouped': documents_grouped,
        'snapshot': deployment.department_status_snapshot or []
    }
    
    return render(request, "indent/deployment_details.html", context)


@login_required
def generate_warranty(request, deployment_id):
    from .models import Deployment
    deployment = get_object_or_404(Deployment, pk=deployment_id)
    context = {
        'deployment': deployment,
        'customer_name': request.GET.get('customer_name', ''),
        'commissioning_date': request.GET.get('commissioning_date', ''),
        'id_number': request.GET.get('id_number', 'HDR0018'),
        'warranty_period': request.GET.get('warranty_period', 'ONE YEAR'),
        'manager_name': request.GET.get('manager_name', 'Karthik Shetty'),
    }
    return render(request, "indent/print/warranty_print.html", context)


@login_required
def generate_guarantee(request, deployment_id):
    from .models import Deployment
    deployment = get_object_or_404(Deployment, pk=deployment_id)
    context = {
        'deployment': deployment,
        'product_name': request.GET.get('product_name', ''),
        'model': request.GET.get('model', ''),
        'id_number': request.GET.get('id_number', 'HDR0018'),
        'valid_until': request.GET.get('valid_until', ''),
        'manager_name': request.GET.get('manager_name', 'Karthik Shetty'),
    }
    return render(request, "indent/print/guarantee_print.html", context)


@login_required
def generate_dc(request, deployment_id):
    from .models import Deployment
    deployment = get_object_or_404(Deployment, pk=deployment_id)

    # Parse subsystem items (item_name_1, item_qty_1, ..., item_name_N, item_qty_N)
    subsystem_items = []
    for i in range(1, 21):
        name = request.GET.get(f'item_name_{i}', '').strip()
        qty = request.GET.get(f'item_qty_{i}', '').strip()
        if name:
            subsystem_items.append({'name': name, 'qty': qty or '1'})

    context = {
        'deployment': deployment,
        # Cover page
        'machine_name': request.GET.get('machine_name', deployment.project.name),
        'date_sent': request.GET.get('date_sent', ''),
        'sender_address_1': request.GET.get('sender_address_1', 'Thimlapura Road, Hurulichikanahalli'),
        'sender_address_2': request.GET.get('sender_address_2', 'Bengaluru 560090'),
        'sender_postcode': request.GET.get('sender_postcode', '560090'),
        # Main DC fields (page 5)
        'dc_no': request.GET.get('dc_no', ''),
        'project_title': request.GET.get('project_title', ''),
        'po_no': request.GET.get('po_no', ''),
        'overall_description': request.GET.get('overall_description', ''),
        # Receiver details
        'receiver_org': request.GET.get('receiver_org', ''),
        'receiver_address': request.GET.get('receiver_address', ''),
        'receiver_postcode': request.GET.get('receiver_postcode', ''),
        'receiver_location': request.GET.get('receiver_location', ''),
        'receiver_email': request.GET.get('receiver_email', ''),
        'receiver_phone': request.GET.get('receiver_phone', ''),
        # Depositor details
        'depositor_name': request.GET.get('depositor_name', ''),
        'depositor_email': request.GET.get('depositor_email', 'services@xpredictlabs.com'),
        'depositor_phone': request.GET.get('depositor_phone', '9901245511'),
        # Sub-system items (page 2)
        'subsystem_items': subsystem_items,
        # Conditions (page 3)
        'conditions_text': request.GET.get('conditions_text', ''),
        # QC / Appendix A (page 4)
        'qc_conclusion': request.GET.get('qc_conclusion', 'All systems tested for a minimum continuous operation as per test procedure set internally.'),
        'run_start_time': request.GET.get('run_start_time', ''),
        'run_start_date': request.GET.get('run_start_date', ''),
        'run_end_time': request.GET.get('run_end_time', ''),
        'run_end_date': request.GET.get('run_end_date', ''),
        'qc_status_report': request.GET.get('qc_status_report', 'Power cable: Normal\nSMPS: Normal\nHMI: Normal\nXCON Controller: Normal\nCurrent Sensors: Normal\nDRS Sensors: Normal\nTimers: Normal\nFluid Systems: Normal, no leaks\nRotary Switches: Normal\nIndicators: Normal\nPumps: Normal\nAir Blower: Normal'),
        'tester_name': request.GET.get('tester_name', ''),
        'examiner_name': request.GET.get('examiner_name', ''),
        # Page 2 fields
        'transfer_info_text': request.GET.get('transfer_info_text', 'Electro Mechanicals\nStructure & Outer Body\nTanks & Plumbing\nSensor Package\nFully Assembled Control Panel\nElectrical and other Components\nOther Sub-Assemblies'),
        'prints_details': request.GET.get('prints_details', 'As provided during installation'),
        'materials_text': request.GET.get('materials_text', ''),
    }
    return render(request, "indent/print/dc_print.html", context)




@login_required
def generate_commissioning(request, deployment_id):
    from .models import Deployment
    deployment = get_object_or_404(Deployment, pk=deployment_id)
    context = {
        'deployment': deployment,
        'client_name': request.GET.get('client_name', 'TATA STEEL LIMITED.'),
        'supplier_name': request.GET.get('supplier_name', 'XPREDICT AUTOMATION SOLUTIONS PVT LTD'),
        'project_name': request.GET.get('project_name', 'HIDREC EC1000 STP'),
        
        # Project Overview
        'scope_of_supply': request.GET.get('scope_of_supply', 'Sewage treatment plant'),
        'po_supply': request.GET.get('po_supply', '2300073076/810'),
        'po_ec': request.GET.get('po_ec', '2300073076/810'),
        
        # Dates
        'supply_completion_date': request.GET.get('supply_completion_date', '11-April-2025'),
        'ic_start_date': request.GET.get('ic_start_date', '17-April-2025'),
        'ic_completion_date': request.GET.get('ic_completion_date', '03-May-2025'),
        'automation_trials_date': request.GET.get('automation_trials_date', '13-May-2025'),
        'commissioning_date': request.GET.get('commissioning_date', '04-June-2025'),
        
        # Lists
        'attendees_client': request.GET.get('attendees_client', 'Mr. Nilesh Bhajan\nMr. Akshat Gupta\nMr. Ramlal (operator)'),
        'attendees_xpredict': request.GET.get('attendees_xpredict', 'Mr. Kushal Dhole\nMr. Madhu S\nMr. Sudeep'),
        'discussion_points': request.GET.get('discussion_points', 'All tasks related to supply, installation, commissioning, automation trials, PLC implementation, safety features, and treatment readiness were completed successfully. Detailed scope items from 01 to 26 have been executed and verified by TSL Team covered in table below.\n\nTreated water sampling is being carried out, STP system maturation for final compliance awaited.'),
        'consumables': request.GET.get('consumables', 'EC Reactor Cells - 4 Nos\nSafety Gear - 3 Sets\nMBBR Media - 3 Bags\nBog Mesh - 20 Nos (1.2 mtr X 1.2 mtr)\nEAOP Reactor Cell - 2 Nos\nPlumbing Items General Spares'),
    }
    return render(request, "indent/print/commissioning_print.html", context)


@login_required
def generate_handover(request, deployment_id):
    from .models import Deployment
    deployment = get_object_or_404(Deployment, pk=deployment_id)
    context = {
        'deployment': deployment,
        'customer_name': request.GET.get('customer_name', ''),
        'handover_date': request.GET.get('handover_date', ''),
        'project_ref': request.GET.get('project_ref', ''),
        'handed_over_by': request.GET.get('handed_over_by', ''),
        'client_rep': request.GET.get('client_rep', ''),
        'dc_no': request.GET.get('dc_no', ''),
        'po_no': request.GET.get('po_no', ''),
        'employee_name': request.GET.get('employee_name', ''),
        'employee_no': request.GET.get('employee_no', ''),
        'location': request.GET.get('location', ''),
        'division': request.GET.get('division', ''),
        'particulars': request.GET.get('particulars', ''),
    }
    return render(request, "indent/print/handover_print.html", context)


@login_required
def attach_generated_doc(request, deployment_id):
    """Save a generated document as an HTML file and attach it to the deployment."""
    import os
    import tempfile
    from django.core.files.base import ContentFile
    from django.template.loader import render_to_string
    from .models import Deployment, DeploymentDocument

    if request.method != 'POST':
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest("POST required")

    deployment = get_object_or_404(Deployment, pk=deployment_id)
    doc_type = request.POST.get('doc_type', '')
    template_map = {
        'warranty': 'indent/print/warranty_print.html',
        'guarantee': 'indent/print/guarantee_print.html',
        'dc': 'indent/print/dc_print.html',
        'commissioning': 'indent/print/commissioning_print.html',
        'handover': 'indent/print/handover_print.html',
    }
    template_name = template_map.get(doc_type)
    if not template_name:
        messages.error(request, "Invalid document type.")
        return redirect('deployment_details', deployment_id=deployment_id)

    # Build context from POST
    context = {'deployment': deployment}
    for key, val in request.POST.items():
        if key not in ('csrfmiddlewaretoken', 'doc_type'):
            context[key] = val

    # Render the template to an HTML string
    html_content = render_to_string(template_name, context, request=request)

    # Save as a file in deployment_docs/
    file_name = f"{doc_type}_{deployment_id}.html"
    doc = DeploymentDocument(deployment=deployment, document_type=doc_type)
    doc.file.save(file_name, ContentFile(html_content.encode('utf-8')), save=True)

    messages.success(request, f"'{doc.get_document_type_display()}' has been attached to the deployment successfully.")
    return redirect(f"{reverse('deployment_details', args=[deployment_id])}#docs")
