from django.forms import modelformset_factory
from django.core.mail import send_mail, EmailMessage
from django.shortcuts import get_object_or_404, render, redirect

from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .views_assembly import (
    generate_warranty, generate_guarantee, generate_dc,
    generate_commissioning, generate_handover, attach_generated_doc
)

from .models import  BOM, GRN, Enquiry, FollowUp, GRNItem, IndentItem,Products,Executive,FileUploadModel, PurchaseItem, PurchaseOrder, PurchaseOrderAttachment, QCCheck, RevertRemark, TelemetryRecord, EmailLog, StockItem, Vendor, VendorStock, StockLog, POPaymentLog, InternalIndent, InternalIndentItem, Department
from django.contrib.auth.models import User
from django.http import JsonResponse,HttpResponse
from django.db.models import Q, ForeignKey, Sum, F, ExpressionWrapper, DecimalField
from decimal import Decimal

from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy

# For PDF Generation
from io import BytesIO
import xhtml2pdf.pisa as pisa
from django.template.loader import get_template
from django.utils import timezone
import openpyxl
from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

class CustomPasswordResetView(auth_views.PasswordResetView):
    template_name = 'xp/home.html'
    email_template_name = 'registration/password_reset_email.html'
    html_email_template_name = 'registration/password_reset_email_html.html'
    success_url = reverse_lazy('login_page')

    def form_valid(self, form):
        messages.success(self.request, "We've emailed you instructions for setting your password, if an account exists with the email you entered. You should receive them shortly.")
        return super().form_valid(form)

class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'xp/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    def get(self, request, *args, **kwargs):
        messages.success(request, "Password has been reset successfully. You can now login with your new password.")
        return redirect('login_page')

# Create your views here.
def home(request):
    if request.user.is_authenticated:
        return redirect('indent_dashboard') # Redirect to Dashboard at /home/

    if request.method == "POST":
        login_input = request.POST.get("email")
        password = request.POST.get("password")
        
        # Try authenticating as username first
        user = authenticate(request, username=login_input, password=password)
        
        # If that fails, try authenticating as email
        if user is None:
            try:
                user_obj = User.objects.filter(email=login_input).first()
                if user_obj:
                    user = authenticate(request, username=user_obj.username, password=password)
            except:
                pass
        
        if user is not None:
            login(request, user)
            return redirect("indent_dashboard") # Redirect to Dashboard
        else:
            messages.error(request, "Invalid email or password")

    return render(request, 'xp/home.html')

from django.contrib.auth import logout as auth_logout
@login_required
def user_logout(request):
    auth_logout(request)
    return redirect("login_page")

def homepage(request):


    return render(request, 'xp/homepage.html')

import random
import datetime
from datetime import timedelta
from django.utils import timezone

@login_required
def dashboard(request):

  # REAL DATA COUNTS
    active_reqs = InternalIndent.objects.count()
    in_production = InternalIndentItem.objects.filter(due_date__gte=timezone.now()).count()
    pending_indents = Indent.objects.filter(status__in=["pending", "draft"]).count()
    completed_items = InternalIndentItem.objects.filter(due_date__lt=timezone.now()).count()

    # DEPARTMENT STATUS
    department_status = []
    for dept in Department.objects.all():
        items = InternalIndentItem.objects.filter(internal_indent__department=dept)

        pending = items.filter(due_date__gte=timezone.now()).count()
        completed = items.filter(due_date__lt=timezone.now()).count()
        overdue = items.filter(due_date__lt=timezone.now() - timedelta(days=3)).count()
        grn_count = InternalIndent.objects.filter(department=dept).count()

        try:
            grn_progress = min(100, int((grn_count / items.count()) * 100))
        except:
            grn_progress = 0

        department_status.append({
            "name": dept.name,
            "pending": pending,
            "completed": completed,
            "overdue": overdue,
            "grn_progress": grn_progress,
        })

    # MATERIAL SHORTAGES
    shortages = []
    for indent in IndentItem.objects.all():
        stock = StockItem.objects.filter(product_name=indent.product_name).first()
        available = stock.quantity if stock else 0
        shortage = max(indent.quantity - available, 0)

        if shortage > 0:
            shortages.append({
                "item": indent.product_name,
                "required": indent.quantity,
                "available": available,
                "shortage": shortage,
            })

    # CHART DATA
    prod_load = [random.randint(10, 25) for _ in range(7)]
    indent_trend = [random.randint(3, 15) for _ in range(7)]

    # GRN TIMELINE (REAL)
    grnTimeline = []

    for grn in GRN.objects.filter(grn_type="internal")[:10]:
        if not grn.internal_indent:
            continue

        start = grn.internal_indent.created_at
        end = datetime.datetime.combine(grn.received_date, datetime.time.min)

        grnTimeline.append({
            "x": f"{grn.internal_indent.department.name} - {grn.grn_number}",
            "y": [
                int(start.timestamp() * 1000),
                int(end.timestamp() * 1000)
            ]
        })

    return render(request, "indent/dashboard.html", {
        "active_reqs": active_reqs,
        "in_production": in_production,
        "pending_indents": pending_indents,
        "completed_items": completed_items,

        "department_status": department_status,
        "shortages": shortages,

        "prod_load": prod_load,
        "indent_trend": indent_trend,
        "grn_timeline": grnTimeline,
    })


from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from .models import Enquiry

def enq_home(request):
    current_user = request.user
    selected_user_id = request.GET.get('user')
    selected_user = None

    if selected_user_id:
        selected_user = User.objects.filter(id=selected_user_id).first()

    # Base query for non-confirmed, non-lost, or reverted enquiries
    base_filter = Q(is_confirmed=False, is_lost=False) | Q(is_reverted=True)

    # Determine which enquiries to show
    if current_user.is_staff or current_user.is_superuser:
        # Staff or superusers see all enquiries
        enquiries = Enquiry.objects.filter(base_filter)
    else:
        # Regular users see their created or assigned enquiries
        enquiries = Enquiry.objects.filter(base_filter).filter(
            Q(created_by=current_user) | Q(executive__name=current_user.username)
        )

    # Global search functionality
    search_query = request.GET.get('search', '')

    if search_query:
        global_filter = Q()

        for field in Enquiry._meta.fields:
            field_name = field.name

            if isinstance(field, ForeignKey):
                related_model = field.related_model
                related_fields = [f.name for f in related_model._meta.fields if f.name != 'id']
                for related_field in related_fields:
                    global_filter |= Q(**{f"{field_name}__{related_field}__icontains": search_query})

            elif field.choices:
                for value, display in dict(field.choices).items():
                    if search_query.lower() in display.lower():
                        global_filter |= Q(**{f"{field_name}": value})

            else:
                global_filter |= Q(**{f"{field_name}__icontains": search_query})

        # Apply the global filter
        enquiries = enquiries.filter(global_filter)

    enquiries = enquiries.order_by('-id')

    # Pagination setup
    paginator = Paginator(enquiries, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Add sequence number for display
    start_sequence_number = (page_obj.number - 1) * paginator.per_page + 1
    for index, enquiry in enumerate(page_obj, start=start_sequence_number):
        enquiry.sequence_number = index
        enquiry.followups_list = list(enquiry.followups.order_by('-fodate', '-fotime'))
        # print(f"{enquiry.id} → Followups: {enquiry.followups.count()}")
        # print(f"Latest followup: {enquiry.latest_followup}")

    return render(request, 'xp/enqhome.html', {
        'page_obj': page_obj,
        'search_query': search_query
    })


def enquiry_view(request):
    users=User.objects.all()
    products=Products.objects.all()
    executive=Executive.objects.all()
    return render(request, 'xp/newenquiry.html',{'products':products , 'users':users,'executive':executive,})

def add_data(request):
    if request.method == "POST":
        # Retrieve form data
        company_name = request.POST.get("companyname")
        customer_name = request.POST.get("customername")
        reference_name = request.POST.get("refrencename")
        email = request.POST.get("email")
        contact = request.POST.get("contact")
        location = request.POST.get("location")
        status = request.POST.get("status")
        product_id = request.POST.get("products")
        subproduct = request.POST.get("subproduct")
        closure_date = request.POST.get("closuredate")
        executive_id = request.POST.get("executive_name")
        remarks = request.POST.get("remarks")
        files = request.FILES.getlist("attachment[]")

        # Validate and fetch related objects
        try:
            executive = Executive.objects.get(id=executive_id)
        except Executive.DoesNotExist:
            return HttpResponse("Invalid Executive selected", status=400)

        try:
            product = Products.objects.get(id=product_id)
        except Products.DoesNotExist:
            return HttpResponse("Invalid Product selected", status=400)

        # Create and save the enquiry record
        enquiry = Enquiry.objects.create(
            companyname=company_name,
            customername=customer_name,
            refrence=reference_name,
            email=email,
            contact=contact,
            location=location,
            status=status,
            products=product,
            subproduct=subproduct,
            closuredate=closure_date,
            executive=executive,
            remarks=remarks,
            created_by=request.user,  # Associate with the logged-in user
        )

        for file in files:
            file_upload = FileUploadModel.objects.create(file=file, name=file.name)
            enquiry.files.add(file_upload)

        enquiry.save()

        # Add visibility for both the logged-in user and selected executive
        enquiry.created_by = request.user  # Ensure the logged-in user is saved as creator
        enquiry.executive = executive  # Ensure the selected executive is assigned
        enquiry.save()

        return redirect("enquries")  # Redirect to enqhome page

    return HttpResponse("Invalid request method", status=405)






def enquiry_details(request, id):
    try:
        # Fetch the enquiry object by id
        enquiry = get_object_or_404(Enquiry, id=id)

        # Fetch only the revert remarks related to this enquiry
        revert_remarks = RevertRemark.objects.filter(enquiry=enquiry).order_by('-created_at')
        print(revert_remarks)
        # Fetch the follow-ups related to this enquiry
        followups = FollowUp.objects.filter(enquiry=enquiry).order_by('-fodate', '-fotime')

        # Files associated with the enquiry
        files = enquiry.files.all()

        # Data to pass to the template
        data = {
            "id": id,
            "companyname": enquiry.companyname,
            "customername": enquiry.customername,
            "refrence": enquiry.refrence,
            "email": enquiry.email,
            "contact": enquiry.contact,
            "location": enquiry.location,
            "status": enquiry.get_status_display() if enquiry.status else "N/A",
            "products": enquiry.products.name if enquiry.products else "N/A",  # Access the product name here
            "subproduct": enquiry.subproduct,
            "closuredate": enquiry.closuredate,
            "executive": enquiry.executive.name if enquiry.executive else "N/A",  # Similarly for executive name
            "remarks": enquiry.remarks,
            "files": files,
            "is_lost": "Lost" if enquiry.is_lost else "Active",
            'followups': followups,  # Pass revert remarks here
        }

        # Handle POST request to add a follow-up
        if request.method == "POST":
            foname = request.POST.get('foname')
            fodate = request.POST.get('fodate')
            fotime = request.POST.get('fotime')

            # Save the follow-up record
            FollowUp.objects.create(
                enquiry=enquiry,
                foname=foname,
                fodate=fodate,
                fotime=fotime
            )

            # Redirect to the same page to display the updated follow-ups
            return redirect('enquiry_details', id=id)

        return render(request, 'xp/enquiry_details.html', {'enquiry_data': data, 'followups': followups , 'revert_remarks': revert_remarks})

    except Enquiry.DoesNotExist:
        return HttpResponse("Enquiry not found", status=404)
    

def enquiry_details(request, id):
    try:
        # Fetch the enquiry object by id
        enquiry = get_object_or_404(Enquiry, id=id)

        # Fetch only the revert remarks related to this enquiry
        revert_remarks = RevertRemark.objects.filter(enquiry=enquiry).order_by('-created_at')
        print(revert_remarks)
        # Fetch the follow-ups related to this enquiry
        followups = FollowUp.objects.filter(enquiry=enquiry).order_by('-fodate', '-fotime')

        # Files associated with the enquiry
        files = enquiry.files.all()

        # Data to pass to the template
        data = {
            "id": id,
            "companyname": enquiry.companyname,
            "customername": enquiry.customername,
            "refrence": enquiry.refrence,
            "email": enquiry.email,
            "contact": enquiry.contact,
            "location": enquiry.location,
            "status": enquiry.get_status_display() if enquiry.status else "N/A",
            "products": enquiry.products.name if enquiry.products else "N/A",  # Access the product name here
            "subproduct": enquiry.subproduct,
            "closuredate": enquiry.closuredate,
            "executive": enquiry.executive.name if enquiry.executive else "N/A",  # Similarly for executive name
            "remarks": enquiry.remarks,
            "files": files,
            "is_lost": "Lost" if enquiry.is_lost else "Active",
            'followups': followups,  # Pass revert remarks here
        }

        # Handle POST request to add a follow-up
        if request.method == "POST":
            foname = request.POST.get('foname')
            fodate = request.POST.get('fodate')
            fotime = request.POST.get('fotime')

            # Save the follow-up record
            FollowUp.objects.create(
                enquiry=enquiry,
                foname=foname,
                fodate=fodate,
                fotime=fotime
            )

            # Redirect to the same page to display the updated follow-ups
            return redirect('enquiry_details', id=id)

        return render(request, 'xp/enquiry_details.html', {'enquiry_data': data, 'followups': followups , 'revert_remarks': revert_remarks})

    except Enquiry.DoesNotExist:
        return HttpResponse("Enquiry not found", status=404)
    

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Indent, StockItem
from .forms import DelayReasonForm, DeliveryForm, IndentForm, IndentItemFormSet, MaterialIssueForm, PurchaseItemForm, PurchaseOrderForm, PurchaseItemFormSet, QCCheckForm, SnagInlineForm, SnagReportForm, VendorForm, DeploymentImageForm


@login_required
def indent_list(request):
    indents = Indent.objects.all().order_by('-created_at').prefetch_related('items', 'items__production_item')
    
    # ---------------------------------------------------------
    # Apply Role-Based Visibility Rules
    # ---------------------------------------------------------
    is_admin = request.user.is_superuser or request.user.is_staff
    has_full_view = is_admin or request.user.groups.filter(name__in=['Stock', 'Production', 'Accounts']).exists()
    
    if not has_full_view:
        # Regular department users only see their own department's indents
        user_departments = request.user.assigned_departments.all()
        indents = indents.filter(department__in=user_departments)

    project_id = request.GET.get("project")

    if project_id:
        indents = indents.filter(project_id=project_id)

    department_id = request.GET.get("department")
    if department_id:
        indents = indents.filter(department_id=department_id)

    for indent in indents:
        indent.has_shortage = False
        for item in indent.items.all():
            stock = StockItem.objects.filter(product_name=item.product_name).first()
            available = stock.quantity if stock else 0
            shortage = max(item.quantity - available, 0)
            if shortage > 0:
                indent.has_shortage = True
                break
                
    is_admin = request.user.is_superuser or request.user.is_staff
    is_stock = request.user.groups.filter(name='Stock').exists()
    is_vendor = request.user.groups.filter(name='Vendor').exists()
    is_accounts = request.user.groups.filter(name='Accounts').exists()
    
    can_view_indent_btn = is_admin or is_stock or is_vendor or is_accounts

    # Prepare stock JSON grouped by department
    departments = Department.objects.all()
    stock_dict = {}
    for d in departments:
        dept_code = None
        dept_name_upper = d.name.strip().upper()
        dept_code_upper = (d.code or "").strip().upper()
        
        # 1. Match by choice key directly
        for key, display in StockItem.DEPARTMENTS:
            if dept_name_upper == key.upper() or dept_code_upper == key.upper():
                dept_code = key
                break
        
        if not dept_code:
            # 2. Match by choice display name
            for key, display in StockItem.DEPARTMENTS:
                if dept_name_upper == display.strip().upper() or dept_code_upper == display.strip().upper():
                    dept_code = key
                    break
        
        if not dept_code:
            # 3. Substring matching
            for key, display in StockItem.DEPARTMENTS:
                if key.upper() in dept_name_upper or dept_name_upper in key.upper():
                    dept_code = key
                    break
                if display.strip().upper() in dept_name_upper or dept_name_upper in display.strip().upper():
                    dept_code = key
                    break
        
        if not dept_code:
            dept_code = d.code or d.name
            
        matched_stock = StockItem.objects.filter(
            department=dept_code
        )
        stock_dict[str(d.id)] = {s.product_name: (s.quantity or 0) for s in matched_stock}
        
    import json
    stock_json = json.dumps(stock_dict)

    return render(request, "indent/indent_list.html", {
        "indents": indents,
        "can_view_indent_btn": can_view_indent_btn,
        "stock_json": stock_json,
    })



@login_required
def indent_edit_ajax(request, pk):
    indent = get_object_or_404(Indent, pk=pk)

    if request.method == "GET":
        sfg_list = []
        from indent.models import InternalIndent, StockItem
        if indent.project and indent.department:
            internal_indent = InternalIndent.objects.filter(project=indent.project, department=indent.department).first()
            if internal_indent:
                raw_sfg_items = list(internal_indent.items.all())
                item_names = [i.item_name for i in raw_sfg_items]
                stock_map = {s.product_name.lower(): s.quantity for s in StockItem.objects.filter(product_name__in=item_names)}
                for sfg in raw_sfg_items:
                    stock_qty = stock_map.get(sfg.item_name.lower(), 0)
                    sfg_list.append({
                        "id": sfg.id,
                        "item_name": sfg.item_name,
                        "quantity": sfg.quantity,
                        "stock_qty": stock_qty
                    })
        return JsonResponse({
            "id": indent.id,
            "title": indent.title,
            "required_date": indent.required_date.strftime("%Y-%m-%d") if indent.required_date else "",
            "department_id": indent.department.id if indent.department else None,
            "sfg_list": sfg_list,
            "items": [
                {
                    "id": item.id,
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit": item.unit,
                    "production_item_id": item.production_item.id if item.production_item else None,
                    "sfg_name": item.production_item.item_name if item.production_item else "-"
                }
                for item in indent.items.all()
            ]
        })

    if request.method == "POST":
        indent.title = request.POST.get("title")
        required_date = request.POST.get("required_date")
        indent.required_date = required_date if required_date else None
        indent.save()

        # Remove existing items
        indent.items.all().delete()

        # Re-create items
        names = request.POST.getlist("product_name[]")
        quantities = request.POST.getlist("quantity[]")
        units = request.POST.getlist("unit[]")
        sfg_ids = request.POST.getlist("production_item[]")

        from indent.models import InternalIndentItem
        for idx, (n, q, u) in enumerate(zip(names, quantities, units)):
            sfg_id = sfg_ids[idx] if idx < len(sfg_ids) else None
            sfg = None
            if sfg_id and sfg_id.isdigit():
                sfg = InternalIndentItem.objects.filter(id=sfg_id).first()
            IndentItem.objects.create(
                indent=indent,
                product_name=n,
                quantity=q,
                unit=u,
                production_item=sfg
            )

        return JsonResponse({"success": True})

@login_required
def department_flow(request):
    departments = Department.objects.all().prefetch_related("indent_set")

    # Group indents under each department
    dept_data = []
    for dept in departments:
        indents = Indent.objects.filter(department=dept)
        dept_data.append({"department": dept, "indents": indents})

    return render(request, "indent/department_flow.html", {
        "dept_data": dept_data,
    })


from django.utils import timezone
from django.contrib import messages
from django.shortcuts import render, redirect
from .models import Indent, IndentItem, StockItem
from django.contrib.auth.decorators import login_required

@login_required
def indent_create(request):
    stock_items = StockItem.objects.all()
    today_str = timezone.now().strftime("%y%m%d")

    # 🔹 Generate next indent number for today
    last_indent = Indent.objects.filter(indent_number__startswith=f"XPIND{today_str}").order_by('id').last()
    if last_indent and last_indent.indent_number:
        last_number = int(last_indent.indent_number[-3:])
    else:
        last_number = 0
    next_indent_number = f"XPIND{today_str}{last_number + 1:03d}"

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description", "")
        department_id = request.POST.get("department")

        # ✅ Get Department object by ID
        department = get_object_or_404(Department, id=department_id)

        required_date = request.POST.get("required_date")
        if not required_date:
            required_date = None

        # ✅ Create indent
        indent = Indent.objects.create(
            title=title,
            remarks=description,
            status="draft",
            created_by=request.user,
            indent_number=next_indent_number,
            department=department,
            required_date=required_date,
        )

        # ✅ Save items
        item_names = request.POST.getlist("item_name[]")
        quantities = request.POST.getlist("quantity[]")
        units = request.POST.getlist("unit[]")

        for i in range(len(item_names)):
            name = item_names[i].strip()
            qty = quantities[i].strip() if i < len(quantities) else ""
            unit = units[i].strip() if i < len(units) else ""

            if name and qty:
                stock = StockItem.objects.filter(product_name=name).first()
                code = stock.product_code if stock else None

                IndentItem.objects.create(
                    indent=indent,
                    product_code=code,
                    product_name=name,
                    quantity=int(qty),
                    unit=unit
                )

        # messages.success(request, f"Indent {indent.indent_number} created successfully!")
        return redirect("indent_list")

    # ✅ Only runs on GET
    departments = Department.objects.all()
    
    # Prepare stock JSON grouped by department
    stock_dict = {}
    for d in departments:
        dept_code = None
        dept_name_upper = d.name.strip().upper()
        dept_code_upper = (d.code or "").strip().upper()
        
        # 1. Match by choice key directly
        for key, display in StockItem.DEPARTMENTS:
            if dept_name_upper == key.upper() or dept_code_upper == key.upper():
                dept_code = key
                break
        
        if not dept_code:
            # 2. Match by choice display name
            for key, display in StockItem.DEPARTMENTS:
                if dept_name_upper == display.strip().upper() or dept_code_upper == display.strip().upper():
                    dept_code = key
                    break
        
        if not dept_code:
            # 3. Substring matching
            for key, display in StockItem.DEPARTMENTS:
                if key.upper() in dept_name_upper or dept_name_upper in key.upper():
                    dept_code = key
                    break
                if display.strip().upper() in dept_name_upper or dept_name_upper in display.strip().upper():
                    dept_code = key
                    break
        
        if not dept_code:
            dept_code = d.code or d.name
            
        matched_stock = StockItem.objects.filter(
            department=dept_code
        )
        stock_dict[str(d.id)] = {s.product_name: (s.quantity or 0) for s in matched_stock}
        
    import json
    stock_json = json.dumps(stock_dict)

    return render(request, "indent/indent_form.html", {
        "stock_items": stock_items,
        "next_indent_number": next_indent_number,
        "departments": departments,
        "stock_json": stock_json,
    })

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, permission_required

@login_required
@permission_required('indent.can_reject_indent', raise_exception=True)
@require_POST
def indent_reject(request, pk):
    indent = get_object_or_404(Indent, pk=pk)

    reason = request.POST.get('reject_reason', '').strip()
    if not reason:
        messages.error(request, "Reject reason is required.")
        return redirect('indent_list')

    indent.status = 'rejected'
    indent.reject_reason = reason
    indent.save()

    # messages.success(request, f"Indent #{indent.id} rejected successfully.")
    return redirect('indent_list')


@login_required
@permission_required('indent.can_approve_indent', raise_exception=True)
def indent_approve(request, pk):
    indent = get_object_or_404(Indent, pk=pk)

    if indent.status != "draft":  
        messages.warning(request, "Indent is already processed.")
        return redirect("indent_list")

    for item in indent.items.all():
        stock = StockItem.objects.filter(product_name=item.product_name).first()

        if stock:
            if stock.quantity >= item.quantity:
                # Enough stock → fully issue
                stock.quantity -= item.quantity
                item.shortage_qty = 0
            else:
                # Partial stock available → consume all, mark shortage
                shortage = item.quantity - stock.quantity
                item.shortage_qty = shortage
                stock.quantity = 0
            stock.save()
        else:
            # No stock at all → full shortage
            item.shortage_qty = item.quantity

        item.save()

    indent.status = "approved"
    indent.save()

    # messages.success(request, "Indent approved, stock reduced, and shortages recorded!")
    return redirect("indent_list")


@login_required
@permission_required('indent.can_convert_to_po', raise_exception=True)
def indent_convert_to_po(request, pk, vendor_id):
    """Create a Purchase Order for a single indent."""
    print(f"DEBUG: Processing indent={pk}, vendor={vendor_id}, method={request.method}")
    try:
        indent = get_object_or_404(Indent, pk=pk)
        vendor = get_object_or_404(Vendor, pk=vendor_id)
        print("DEBUG: Indent and Vendor found.")
    except Exception as e:
        print(f"DEBUG: Error retrieving Indent or Vendor: {e}")
        raise
    
    # Show all approved items for this vendor, regardless of shortage (user can decide quantity)
    vendor_items = indent.items.filter(approved=True, rejected=False, vendor_id=vendor_id)
    print(f"DEBUG: Found {vendor_items.count()} matching items for vendor {vendor_id} in indent {pk}")
    for i in indent.items.all():
         print(f"DEBUG: Item {i.product_name} | Approved: {i.approved} | Rejected: {i.rejected} | Shortage: {i.shortage_qty} | Vendor: {i.vendor_id}")

    if not vendor_items.exists():
        messages.error(request, "No approved items with shortage for this vendor.")
        return redirect("indent_details", indent_id=indent.id)
    
    aggregated_items = []
    for item in vendor_items:
        # Fetch last purchased info
        # Fetch last purchased info
        clean_name = item.product_name.strip()
        last_po_item = PurchaseItem.objects.filter(
            product_name__iexact=clean_name
        ).exclude(
            po__status='rejected'
        ).select_related('po').order_by('-po__created_at').first()
        
        last_price = last_po_item.unit_price if last_po_item else None
        last_date = last_po_item.po.created_at if last_po_item else None
        
        # Prefill unit_price with last purchased price if available, else indent price
        prefill_price = last_price if last_price else item.unit_price

        aggregated_items.append({
            "product_code": item.product_code,
            "product_name": item.product_name,
            "quantity": item.shortage_qty,
            "unit_price": prefill_price,
            "remarks": item.remarks or "",
            "indent_qty": item.quantity,
            "available": (StockItem.objects.filter(product_name=item.product_name).first().quantity if StockItem.objects.filter(product_name=item.product_name).first() else 0),
            "shortage": item.shortage_qty,
            "last_purchased_price": last_price,
            "last_purchased_date": last_date,
        })

    # --- AUTO-GENERATE PO NUMBER ---
    today_str = timezone.now().strftime("%y%m%d")
    last_po = PurchaseOrder.objects.filter(po_number__startswith=f"XPPO{today_str}").order_by('id').last()
    last_number = int(last_po.po_number[-3:]) if last_po else 0
    auto_po_number = f"XPPO{today_str}{last_number + 1:03d}"

    if request.method == 'POST':
        po_form = PurchaseOrderForm(request.POST, request.FILES)
        item_formset = PurchaseItemFormSet(request.POST)
        if po_form.is_valid() and item_formset.is_valid():
            with transaction.atomic():
                po = po_form.save(commit=False)
                po.indent = indent
                po.vendor = vendor
                po.po_number = auto_po_number
                if not po.payment_terms:
                    po.payment_terms = 'Credit'
                
                # Explicitly set last_bought_value to ensure it is saved
                if 'last_bought_value' in po_form.cleaned_data:
                    po.last_bought_value = po_form.cleaned_data['last_bought_value']
                
                # Assign single proforma_invoice field if any file uploaded, for backward compatibility
                # attachments field returns a list of files or None
                files = po_form.cleaned_data.get('attachments')
                # Removed backward compatibility assignment to proforma_invoice to prevent file consumption/move issues.
                # Use PurchaseOrderAttachment for all files.
                
                po.save()

                # Save all attachments
                if files and isinstance(files, list):
                    for f in files:
                        PurchaseOrderAttachment.objects.create(purchase_order=po, file=f)

                for form, data in zip(item_formset, aggregated_items):
                    if not form.cleaned_data:
                        continue
                    PurchaseItem.objects.create(
                        po=po,
                        product_code=data["product_code"],
                        product_name=form.cleaned_data.get("product_name", data["product_name"]),
                        quantity=form.cleaned_data.get("quantity", data["quantity"]),
                        unit_price=form.cleaned_data.get("unit_price", data.get("unit_price", 0)),
                        remarks=form.cleaned_data.get("remarks", data.get("remarks", "")),
                    )
                messages.success(request, f"Purchase Order {po.po_number} created successfully.")
                return redirect("purchase_order_list")
        else:
            messages.error(request, f"Error creating PO. Please check the form. Errors: {po_form.errors} {item_formset.errors}")
    else:
        po_form = PurchaseOrderForm(initial={
            'po_number': auto_po_number,
            'vendor': vendor.id,
            'vendor_name': vendor.name,
            'vendor_code': vendor.code,
            'payment_terms': 'Credit',  # Set default initial value
        })

    PurchaseItemFormSetWithExtra = modelformset_factory(
        PurchaseItem,
        form=PurchaseItemForm,
        extra=len(aggregated_items),
        can_delete=False
    )
    item_formset = PurchaseItemFormSetWithExtra(queryset=PurchaseItem.objects.none(), initial=aggregated_items)
    formset_items = zip(item_formset.forms, aggregated_items)
    return render(request, "indent/po_form.html", {
        "po_form": po_form,
        "item_formset": item_formset,
        "formset_items": formset_items,
        "indent": indent,
        "vendor": vendor,
    })


from django.views.decorators.clickjacking import xframe_options_exempt

@xframe_options_exempt
@login_required
def purchase_order_print(request, po_id):
    po = get_object_or_404(PurchaseOrder, id=po_id)

    items = po.items.all()

    total_amount = sum(
        (item.quantity or 0) * (item.unit_price or 0)
        for item in items
    )

    company = {
        "name": "Xpredict Automation Solutions Pvt Ltd",
        "address": "Thimlapura Road, Hurulichikanahalli, Bengaluru 560090",
        "phone": "7795625583",
        "email": "info@xpredictlabs.com",
        "gst": "29AAACX2581L1ZU",
        "pan": "AAACX2581L",
        "logo": "static/xlogo.jpeg"  # adjust if needed
    }

    return render(request, "indent/po_print.html", {
        "po": po,
        "items": items,
        "company": company,
        "total_amount": total_amount,
        "vendor": po.vendor,  # 🔥 Explicitly pass vendor object
    })


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Vendor

@login_required
def vendor_autocomplete(request):
    q = request.GET.get("q", "")
    vendors = Vendor.objects.filter(name__icontains=q)[:10]
    results = [{"name": v.name, "code": v.code} for v in vendors]
    return JsonResponse(results, safe=False)



# @login_required
# def stock_list(request):
#     stock_items = StockItem.objects.all().order_by('product_name')
#     return render(request, "indent/stock_list.html", {"stock_items": stock_items})


@login_required
@permission_required('indent.can_manage_stock', raise_exception=True)
def stock_list(request):
    if request.method == "POST":
        if 'add_vendor_stock' in request.POST:
            stock_id = request.POST.get("stock_id")
            vendor_id = request.POST.get("vendor_id")
            price = request.POST.get("price")
            lead_time = request.POST.get("lead_time")

            stock = get_object_or_404(StockItem, pk=stock_id)
            vendor = get_object_or_404(Vendor, pk=vendor_id)

            VendorStock.objects.update_or_create(
                stock_item=stock,
                vendor=vendor,
                defaults={'price': price, 'lead_time': lead_time}
            )
            return redirect("stock_list")

        name = request.POST.get("product_name", "").strip()
        qty_str = request.POST.get("quantity", "").strip()
        stock_type = request.POST.get("stock_type", "").strip()
        department = request.POST.get("department", "").strip()
        min_stock = request.POST.get("min_stock", "0")

        if name and qty_str.isdigit():
            qty = int(qty_str)

            stock, created = StockItem.objects.get_or_create(
                product_name=name,
                defaults={
                    "quantity": qty,
                    "stock_type": stock_type,
                    "department": department,
                    "min_stock": min_stock,
                }
            )

            if created:
                StockLog.objects.create(
                    stock_item=stock,
                    change_quantity=qty,
                    transaction_type='ADD',
                    description=f"Initial stock creation: {qty}",
                    user=request.user
                )
            else:
                diff = qty - stock.quantity
                if diff != 0:
                     StockLog.objects.create(
                        stock_item=stock,
                        change_quantity=diff,
                        transaction_type='ADJUSTMENT',
                        description=f"Manual update: {stock.quantity} -> {qty}",
                        user=request.user
                    )
                stock.quantity = qty
                stock.stock_type = stock_type
                stock.department = department
                stock.min_stock = min_stock

            stock.save()

            # Handle Initial Vendor Details (Supports Multiple)
            initial_vendor_ids = request.POST.getlist("initial_vendor_id[]") or request.POST.getlist("initial_vendor_id")
            initial_prices = request.POST.getlist("initial_price[]") or request.POST.getlist("initial_price")
            initial_lead_times = request.POST.getlist("initial_lead_time[]") or request.POST.getlist("initial_lead_time")

            # Fallback for single values if not passed as list
            if not initial_vendor_ids:
                single_vendor = request.POST.get("initial_vendor_id")
                if single_vendor:
                    initial_vendor_ids = [single_vendor]
                    initial_prices = [request.POST.get("initial_price")]
                    initial_lead_times = [request.POST.get("initial_lead_time")]

            for idx, v_id in enumerate(initial_vendor_ids):
                price = initial_prices[idx] if idx < len(initial_prices) else None
                lead_time = initial_lead_times[idx] if idx < len(initial_lead_times) else "0"

                if v_id and price:
                    try:
                        vendor = Vendor.objects.get(pk=v_id)
                        VendorStock.objects.update_or_create(
                            stock_item=stock,
                            vendor=vendor,
                            defaults={
                                'price': price,
                                'lead_time': lead_time or 0
                            }
                        )
                    except Vendor.DoesNotExist:
                        pass

            return redirect("stock_list")
        else:
            messages.error(request, "Invalid product name or quantity.")

    stocks = StockItem.objects.prefetch_related('vendor_mappings__vendor', 'logs').order_by("product_name")
    vendors = Vendor.objects.all()
    return render(request, "indent/stock_list.html", {"stocks": stocks, "vendors": vendors})



from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages

@login_required
def purchase_order_list(request):
    pos = PurchaseOrder.objects.select_related("indent").prefetch_related("items", "attachments").order_by("-created_at")

    project_id = request.GET.get("project")
    project = None
    if project_id:
        project = get_object_or_404(Project, id=project_id)
        pos = pos.filter(indent__project_id=project_id)

    department_id = request.GET.get("department")
    department = None
    if department_id:
        department = get_object_or_404(Department, id=department_id)
        pos = pos.filter(indent__department_id=department_id)

    # Handle send to vendor POST action
    if request.method == "POST":
        po_id = request.POST.get("send_to_vendor_id")
        po = get_object_or_404(PurchaseOrder, id=po_id)
        
        # --- WHATSAPP LOGIC ---
        if request.POST.get("send_via_whatsapp"):
            recipient_number = request.POST.get("whatsapp_number")
            message_body = request.POST.get("whatsapp_message")
            
            # Log the WhatsApp message
            WhatsAppLog.objects.create(
                purchase_order=po,
                recipient_number=recipient_number,
                message=message_body,
                sent_by=request.user
            )
            
            po.sent_to_vendor = True
            po.save()
            messages.success(request, f"WhatsApp logged for PO #{po.po_number}")


        if request.POST.get("send_via_email"):
            email_to = request.POST.get("email_to")
            email_subject = request.POST.get("email_subject")
            email_body = request.POST.get("email_body")
            

            try:
                msg = EmailMessage(
                    email_subject,
                    email_body,
                    'xpredictdigitalcontrols@gmail.com',
                    [email_to]
                )

                # --- Auto-generate and Attach PO PDF ---
                # Re-use logic from purchase_order_print view
                company = {
                    "name": "Xpredict Automation Solutions Pvt Ltd",
                    "address": "Thimlapura Road, Hurulichikanahalli, Bengaluru 560090",
                    "phone": "7795625583",
                    "email": "info@xpredictlabs.com",
                    "gst": "29AAACX2581L1ZU",
                    "pan": "AAACX2581L",
                    "logo": "static/xlogo.jpeg"  # Ensure this path is available or use full path if needed
                }
                
                # Render the template
                template_path = 'indent/po_print.html'
                context = {
                    'po': po,
                    'items': po.items.all(),
                    'company': company,
                    'total_amount': sum((item.quantity or 0) * (item.unit_price or 0) for item in po.items.all())
                }
                template = get_template(template_path)
                html = template.render(context)
                
                # Create PDF
                result = BytesIO()
                pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
                
                if not pdf.err:
                    msg.attach(f'Purchase_Order_{po.po_number}.pdf', result.getvalue(), 'application/pdf')
                else:
                    messages.warning(request, "Failed to generate PDF attachment, sending email without it.")

                # --- Manual Attachment ---
                if "email_attachment" in request.FILES:
                    attachment = request.FILES["email_attachment"]
                    # Calculate position 0 for re-reading if needed, but Django handles file field saving 
                    # from the same InMemoryUploadedFile object usually fine if we don't consume it fully 
                    # or if we reset it. 
                    # However, msg.attach() reads it. So we must Seek.
                    content = attachment.read()
                    msg.attach(attachment.name, content, attachment.content_type)
                    attachment.seek(0) # Reset for model saving
                
                msg.send(fail_silently=False)

                # Log the email
                EmailLog.objects.create(
                    purchase_order=po,
                    recipient=email_to,
                    subject=email_subject,
                    body=email_body,
                    attachment=request.FILES.get("email_attachment")
                )

                messages.success(request, f"Email sent to {email_to}!")
                po.sent_to_vendor = True
                po.save()
            except Exception as e:
                messages.error(request, f"Failed to send email: {str(e)}")
                # We do NOT mark as sent if email failed, so user can try again.
        
        elif po.status == "approved" and not po.sent_to_vendor:
            # Just mark as sent (e.g. WhatsApp or manual)
            po.sent_to_vendor = True
            po.save()
            # messages.success(request, f"PO {po.po_number} sent to vendor {po.vendor}!")

        # else:
        #     messages.warning(request, "PO not in approved state or already sent.")

        return redirect("po_list")  # adjust the URL name accordingly

    is_admin = request.user.is_superuser or request.user.is_staff
    is_accounts = request.user.groups.filter(name='Accounts').exists()

    return render(request, "indent/purchase_order_list.html", {
        "pos": pos,
        "project": project,
        "department": department,
        "is_admin": is_admin,
        "is_accounts": is_accounts
    })


@login_required
def purchase_order_detail(request, pk):
    po = get_object_or_404(PurchaseOrder.objects.prefetch_related("items"), pk=pk)
    
    company = {
        "name": "Xpredict Automation Solutions Pvt Ltd",
        "address": "Thimlapura Road, Hurulichikanahalli, Bengaluru 560090",
        "phone": "7795625583",
        "email": "info@xpredictlabs.com",
        "gst": "29AAACX2581L1ZU",
        "pan": "AAACX2581L",
        "logo": "static/xlogo.jpeg"
    }
    
    total_amount = po.get_grand_total()
    
    return render(request, "indent/purchase_order_detail.html", {
        "po": po,
        "company": company,
        "total_amount": total_amount,
        "vendor": po.vendor
    })


from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .models import PurchaseOrder

@login_required
def purchase_order_approve(request, pk):
    is_admin = request.user.is_superuser or request.user.is_staff
    is_accounts = request.user.groups.filter(name='Accounts').exists()
    if not (is_admin or is_accounts):
        messages.error(request, "Only Accounts and Admin users can approve POs.")
        return redirect('purchase_order_list')

    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status != 'pending':
        messages.warning(request, "Purchase order cannot be approved.")
        return redirect('purchase_order_list')

    po.status = 'approved'
    po.reject_reason = None
    po.save()
    # messages.success(request, f"PO #{po.po_number} approved successfully.")
    return redirect('purchase_order_list')

@login_required
@require_POST
def purchase_order_reject(request, pk):
    is_admin = request.user.is_superuser or request.user.is_staff
    is_accounts = request.user.groups.filter(name='Accounts').exists()
    if not (is_admin or is_accounts):
        messages.error(request, "Only Accounts and Admin users can reject POs.")
        return redirect('purchase_order_list')

    po = get_object_or_404(PurchaseOrder, pk=pk)

    reason = request.POST.get('reject_reason', '').strip()
    if not reason:
        messages.error(request, "Reject reason is required.")
        return redirect('purchase_order_list')

    po.status = 'rejected'
    po.reject_reason = reason
    po.save()
    # messages.success(request, f"PO #{po.po_number} rejected successfully.")
    return redirect('purchase_order_list')


from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from .models import Vendor, VendorRating, WhatsAppLog

@login_required
def vendor_rate(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk)

    if request.method == 'POST':
        rating_val = request.POST.get('rating')
        comments = request.POST.get('comments', '').strip()

        try:
            rating_val = float(rating_val)
            if rating_val < 0.5 or rating_val > 5:
                raise ValueError()
        except (TypeError, ValueError):
            messages.error(request, "Invalid rating value.")
            return redirect('vendor_list')

        VendorRating.objects.update_or_create(
            vendor=vendor,
            user=request.user,
            defaults={'rating': rating_val, 'comments': comments}
        )

        messages.success(request, f"Thank you for rating {vendor.name}!")
        return redirect('vendor_list')

    return redirect('vendor_list')


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Vendor

@login_required
@permission_required('indent.can_manage_vendor', raise_exception=True)
def vendor_list(request):
    vendors = Vendor.objects.all()

    if request.method == "POST":

        # CREATE VENDOR
        if "create_vendor" in request.POST:
            name = request.POST.get("name")
            level = request.POST.get("level")
            contact_email = request.POST.get("contact_email")
            contact_number = request.POST.get("contact_number")
            contact_number_2 = request.POST.get("contact_number_2")
            category = request.POST.get("category")
            gst_number = request.POST.get("gst_number")
            pan_number = request.POST.get("pan_number")
            bank_name = request.POST.get("bank_name")
            bank_account_no = request.POST.get("bank_account_no")
            ifsc_code = request.POST.get("ifsc_code")
            credit_period_days = request.POST.get("credit_period_days", 30)

            if not name or not level:
                messages.error(request, "Name and Level are required!")
            else:
                vendor = Vendor.objects.create(
                    name=name,
                    level=level,
                    contact_email=contact_email,
                    contact_number=contact_number,
                    contact_number_2=contact_number_2,
                    category=category,
                    gst_number=gst_number,
                    pan_number=pan_number,
                    bank_name=bank_name,
                    bank_account_no=bank_account_no,
                    ifsc_code=ifsc_code,
                    credit_period_days=credit_period_days,
                )
                return redirect("vendor_list")

        # EDIT VENDOR
        elif "edit_vendor" in request.POST:
            vendor_id = request.POST.get("edit_vendor_id")
            vendor = get_object_or_404(Vendor, id=vendor_id)

            name = request.POST.get("name")
            level = request.POST.get("level")
            contact_email = request.POST.get("contact_email")
            contact_number = request.POST.get("contact_number")
            contact_number_2 = request.POST.get("contact_number_2")
            category = request.POST.get("category")
            gst_number = request.POST.get("gst_number")
            pan_number = request.POST.get("pan_number")
            bank_name = request.POST.get("bank_name")
            bank_account_no = request.POST.get("bank_account_no")
            ifsc_code = request.POST.get("ifsc_code")
            credit_period_days = request.POST.get("credit_period_days", 30)

            if not name or not level:
                messages.error(request, "Name and Level are required!")
            else:
                vendor.name = name
                vendor.level = level
                vendor.contact_email = contact_email
                vendor.contact_number = contact_number
                vendor.contact_number_2 = contact_number_2
                vendor.category = category
                vendor.gst_number = gst_number
                vendor.pan_number = pan_number
                vendor.bank_name = bank_name
                vendor.bank_account_no = bank_account_no
                vendor.ifsc_code = ifsc_code
                vendor.credit_period_days = credit_period_days
                vendor.save()

                # messages.success(request, f"Vendor '{vendor.name}' updated successfully!")
                return redirect("vendor_list")

    context = {
        "vendors": vendors,
    }
    return render(request, "indent/vendor_list.html", context)



import datetime
from django.shortcuts import render
from .models import PurchaseOrder

def po_list(request):
    today = datetime.date.today()

    # Filter only those sent to vendor
    purchase_orders = PurchaseOrder.objects.filter(sent_to_vendor=True)

    # Calculate overdue days if applicable
    for po in purchase_orders:
        if po.expected_delivery and po.status == 'approved':
            delta = (today - po.expected_delivery).days
            po.overdue_days = delta if delta > 0 else 0
        else:
            po.overdue_days = 0

    return render(request, 'indent/po_list.html', {
        'purchase_orders': purchase_orders,
        'today': today,
    })


@login_required
def po_update_delay(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)

    if request.method == 'POST':
        form = DelayReasonForm(request.POST, instance=po)
        if form.is_valid():
            form.save()
            # messages.success(request, "Delay reason updated.")
            return redirect('po_list')
    else:
        form = DelayReasonForm(instance=po)

    return render(request, 'indent/po_update_delay.html', {'form': form, 'po': po})


from django.shortcuts import render
from django.http import JsonResponse
import json
from collections import defaultdict

def index(request):
    print("GOT HIT")
    return render(request, "canvas_app/index.html")

def generate_bom(request):
    if request.method == "POST":
        data = json.loads(request.body)

        bom_summary = defaultdict(lambda: {"count": 0, "material": None, "size": None})

        for item in data.get("items", []):
            key = f"{item['material']} - {item['size']}"
            bom_summary[key]["count"] += 1
            bom_summary[key]["material"] = item["material"]
            bom_summary[key]["size"] = item["size"]

        bom_list = [
            {"material": v["material"], "size": v["size"], "quantity": v["count"]}
            for v in bom_summary.values()
        ]
        return JsonResponse({"bom": bom_list})
    
from django.db import models, transaction
from django.utils import timezone
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required

@login_required
def create_grn(request, po_id):
    po = get_object_or_404(PurchaseOrder, id=po_id)

    if request.method == "POST":
        with transaction.atomic():
            # --- Generate unique GRN ---
            today_str = timezone.now().strftime("%y%m%d")
            last_grn = (
                GRN.objects.select_for_update()
                .filter(grn_number__startswith=f"XPGRN{today_str}")
                .order_by("id")
                .last()
            )
            last_number = int(last_grn.grn_number[-3:]) if last_grn else 0
            auto_grn_number = f"XPGRN{today_str}{last_number + 1:03d}"

            grn = GRN.objects.create(
                po=po,
                grn_number=auto_grn_number,
                received_date=request.POST.get("received_date"),
                created_by=request.user,
                attachment=request.FILES.get("attachment"),
            )

            fully_received = True

            for item in po.items.all():
                received_qty = int(request.POST.get(f"received_qty_{item.id}", 0))
                accepted_qty = int(request.POST.get(f"accepted_qty_{item.id}", 0))
                rejected_qty = int(request.POST.get(f"rejected_qty_{item.id}", 0))
                rejection_reason = request.POST.get(f"rejection_reason_{item.id}", "")

                # ✅ Ensure consistency: accepted + rejected = received
                if accepted_qty + rejected_qty != received_qty:
                    messages.error(
                        request,
                        f"Accepted + Rejected qty must equal Received qty for {item.product_name}.",
                    )
                    transaction.set_rollback(True)
                    return redirect("create_grn", po_id=po.id)

                # ✅ Prevent over receiving logic removed as per user request to allow extra quantities
                # already_received = (
                #     GRNItem.objects.filter(purchase_item=item).aggregate(
                #         total=models.Sum("received_quantity")
                #     )["total"]
                #     or 0
                # )
                # remaining_qty = item.quantity - already_received
                # if received_qty > remaining_qty:
                #     received_qty = remaining_qty
                #     # adjust if mismatch happens
                #     if accepted_qty + rejected_qty > received_qty:
                #         accepted_qty = min(accepted_qty, received_qty)
                #         rejected_qty = received_qty - accepted_qty

                if received_qty > 0:
                    grn_item = GRNItem.objects.create(
                        grn=grn,
                        purchase_item=item,
                        received_quantity=received_qty,
                        accepted_qty=accepted_qty,
                        rejected_qty=rejected_qty,
                        rejection_reason=rejection_reason,
                    )


                # --- The status is now handled automatically by GRNItem.save() calling grn.update_po_status() ---
                pass

            # messages.success(request, f"GRN {grn.grn_number} created successfully!")
            return redirect(f"/indent/grn/?project_id={po.indent.project.id}")

    # ---- Prepare form context ----
    po_items = []
    for item in po.items.all():
        already_received = (
            GRNItem.objects.filter(purchase_item=item).aggregate(
                total=models.Sum("accepted_qty")
            )["total"]
            or 0
        )
        pending = item.quantity - already_received
        po_items.append(
            {
                "id": item.id,
                "product_code": item.product_code,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "already_received": already_received,
                "pending": pending,
            }
        )

    # ✅ Auto-generate GRN for form load
    today_str = timezone.now().strftime("%y%m%d")
    last_grn = (
        GRN.objects.filter(grn_number__startswith=f"XPGRN{today_str}")
        .order_by("id")
        .last()
    )
    last_number = int(last_grn.grn_number[-3:]) if last_grn else 0
    auto_grn_number = f"XPGRN{today_str}{last_number + 1:03d}"

    return render(
        request,
        "indent/create_grn.html",
        {"po": po, "auto_grn_number": auto_grn_number, "po_items": po_items},
    )
from django.utils.safestring import mark_safe

@login_required
def grn_list(request):
    project_id = request.GET.get("project_id")
    department_id = request.GET.get("department_id")

    # ---------------------------------------
    # 1️⃣ FILTER PURCHASE ORDER GRNs BY PROJECT + DEPT
    # ---------------------------------------
    pos = PurchaseOrder.objects.filter(
        status__in=["approved", "partially_received", "received"]
    ).select_related(
        "vendor", "indent", "indent__project"
    ).prefetch_related(
        "items", 
        "grns__items", 
        "grns__items__purchase_item", 
        "grns__created_by"
    )

    if project_id:
        pos = pos.filter(indent__project_id=project_id)

    if department_id:
        pos = pos.filter(indent__department_id=department_id)

    def get_progress_html(progress, is_complete):
        color = "bg-success" if is_complete else "bg-primary"
        return mark_safe(f"""
            <div class="d-flex align-items-center gap-2" style="min-width: 120px;">
                <div class="progress flex-grow-1" style="height: 6px;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated {color}" role="progressbar" style="width:{progress}%;"></div>
                </div>
                <span class="fw-bold text-muted" style="font-size: 0.75rem;">{progress}%</span>
            </div>
        """)

    def get_user_badge_html(user):
        if not user: return ""
        initial = user.username[:1].upper()
        return mark_safe(f"""
            <div class="d-flex align-items-center gap-1">
                <span class="badge bg-blue text-white rounded-circle p-1" style="width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center; font-size: 0.6rem;">{initial}</span>
                <span class="small">{user.username}</span>
            </div>
        """)

    # Attach summary stats to each PO for template display
    for po in pos:
        po.total_ordered = sum(item.quantity for item in po.items.all())
        
        # Track total accepted per item for progress display
        item_accepted_map = {}
        po.total_accepted = 0
        po.total_rejected = 0
        
        for grn in po.grns.all():
            for grn_item in grn.items.all():
                po.total_accepted += grn_item.accepted_qty
                po.total_rejected += grn_item.rejected_qty
                pid = grn_item.purchase_item_id
                item_accepted_map[pid] = item_accepted_map.get(pid, 0) + grn_item.accepted_qty

        # Calculate PO-level percentage progress first
        if po.total_ordered > 0:
            po.percent_complete = round((po.total_accepted / po.total_ordered) * 100, 1)
        else:
            po.percent_complete = 0

        # Pre-render PO display components
        status_class = "bg-success" if po.status == 'received' else "bg-secondary"
        po.status_badge_html = mark_safe(f'<span class="badge text-white {status_class}">{po.get_status_display()}</span>')

        prog_class = "bg-success" if po.percent_complete >= 100 else "bg-info"
        po.progress_html = mark_safe(f'''
            <div class="progress progress-xs" style="width: 100px; height: 8px;">
                <div class="progress-bar progress-bar-striped progress-bar-animated {prog_class}" role="progressbar" style="width:{po.percent_complete}%;"></div>
            </div>
            <span class="text-muted" style="font-size: 0.75rem;">{po.percent_complete}%</span>
        ''')

        from django.urls import reverse
        action_parts = []
        if po.status != "received":
            create_url = reverse('create_grn', args=[po.id])
            action_parts.append(f'<a href="{create_url}" class="btn btn-sm btn-success">Create GRN</a>')
        else:
            action_parts.append('<button class="btn btn-sm btn-secondary" disabled>Received</button>')
        
        if po.grns.exists():
            action_parts.append(f'<button class="btn btn-sm btn-outline-primary" type="button" data-bs-toggle="collapse" data-bs-target="#grnHistory{po.id}">History</button>')
        
        po.action_html = mark_safe(f'<div class="d-flex justify-content-center gap-1">{"".join(action_parts)}</div>')

        # Attach pre-rendered rows to each GRN
        for grn in po.grns.all():
            grn.user_badge_html = get_user_badge_html(grn.created_by)
            grn.date_str = grn.received_date.strftime("%Y-%m-%d") if grn.received_date else "-"
            
            for f_item in grn.items.all():
                total_for_item = item_accepted_map.get(f_item.purchase_item_id, 0)
                ordered_for_item = f_item.purchase_item.quantity
                
                disp_name = f_item.purchase_item.product_name or "Product"
                disp_code = f_item.purchase_item.product_code
                
                if ordered_for_item > 0:
                    item_prog = round((total_for_item / ordered_for_item) * 100, 1)
                else:
                    item_prog = 0
                
                # Pre-render the entire <tr> content
                rej_html = f'<div class="text-danger small mt-1" style="font-size: 0.75rem;">{f_item.rejection_reason}</div>' if f_item.rejection_reason else ''
                
                # Progress Bar HTML
                prog_bar_class = "bg-success" if item_prog >= 100 else "bg-info"
                prog_html = f'''
                    <div class="progress" style="height: 12px; min-width: 80px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated {prog_bar_class}" role="progressbar" style="width: {item_prog}%" aria-valuenow="{item_prog}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <small class="text-muted d-block text-center" style="font-size: 0.7rem;">{item_prog}%</small>
                '''

                f_item.rendered_row_html = mark_safe(f'''
                    <tr class="align-middle">
                        <td><span class="badge bg-light text-dark border">{grn.grn_number}</span></td>
                        <td><div class="fw-bold">{disp_name}</div><small class="text-muted">{disp_code or ""}</small></td>
                        <td class="text-center fw-bold text-primary">{ordered_for_item}</td>
                        <td class="text-center">{f_item.received_quantity}</td>
                        <td class="text-center"><span class="badge bg-success text-white px-2">{f_item.accepted_qty}</span></td>
                        <td class="text-center"><span class="badge bg-danger text-white px-2">{f_item.rejected_qty}</span>{rej_html}</td>
                        <td>{prog_html}</td>
                        <td class="small">{grn.date_str}</td>
                        <td>{grn.user_badge_html}</td>
                    </tr>
                ''')


    # ---------------------------------------
    # 2️⃣ FILTER INTERNAL INDENTS BY PROJECT + DEPT
    # ---------------------------------------
    internal_indents = InternalIndent.objects.all().prefetch_related(
        "items", 
        "internal_grns__items",
        "internal_grns__items__internal_indent_item",
        "internal_grns__created_by"
    )

    if project_id:
        internal_indents = internal_indents.filter(project_id=project_id)

    if department_id:
        internal_indents = internal_indents.filter(department_id=department_id)

    # 3️⃣ Prepare internal indent item-level GRN summary
    indent_data = []

    for indent in internal_indents:

        items_data = []
        pending_exists = False

        # Pre-calculate totals to avoid N+1 inside item loop
        received_map = {}
        accepted_map = {}
        for igrn in indent.internal_grns.all():
            for grn_item in igrn.items.all():
                iid = grn_item.internal_indent_item_id
                received_map[iid] = received_map.get(iid, 0) + grn_item.received_quantity
                accepted_map[iid] = accepted_map.get(iid, 0) + grn_item.accepted_qty

        for item in indent.items.all():
            total_received = received_map.get(item.id, 0)
            pending_qty = item.quantity - total_received
            if pending_qty > 0:
                pending_exists = True

            items_data.append({
                "item": item,
                "requested": item.quantity,
                "received": total_received,
                "pending": pending_qty,
            })

        # Pre-render Action buttons for Internal Indent
        from django.urls import reverse
        action_html = []
        if pending_exists:
            create_url = reverse('create_internal_grn', args=[indent.id])
            action_html.append(f'<a href="{create_url}" class="btn btn-sm btn-success">Create Internal GRN</a>')
        else:
            action_html.append('<button class="btn btn-sm btn-secondary" disabled>Create Internal GRN</button>')
        
        if indent.internal_grns.exists():
            action_html.append(f'<button class="btn btn-sm btn-primary" data-bs-toggle="collapse" data-bs-target="#igrnHistory{indent.id}">View IGRN History</button>')
        else:
            action_html.append('<button class="btn btn-sm btn-primary" disabled>View IGRN History</button>')
        
        indent.action_buttons_html = mark_safe(f'<div class="d-flex justify-content-center gap-2">{"".join(action_html)}</div>')

        # Prepare summary table rows as safe HTML
        indent.summary_rows_html = mark_safe("".join([
            f'<tr><td>{item_data["item"].item_name}</td><td>{item_data["requested"]}</td><td class="text-success fw-bold">{item_data["received"]}</td><td class="text-danger fw-bold">{item_data["pending"]}</td></tr>'
            for item_data in items_data
        ]))

        # Attach item progress and pre-rendered HTML to each Internal GRN row
        for i_grn in indent.internal_grns.all():
            i_grn.user_badge_html = get_user_badge_html(i_grn.created_by)
            i_grn.date_str = i_grn.received_date.strftime("%Y-%m-%d") if i_grn.received_date else "-"
            
            for i_item in i_grn.items.all():
                i_total = accepted_map.get(i_item.internal_indent_item_id, 0)
                i_ordered = i_item.internal_indent_item.quantity
                
                i_name = i_item.internal_indent_item.item_name or "Item"
                
                if i_ordered > 0:
                    i_prog = round((i_total / i_ordered) * 100, 1)
                else:
                    i_prog = 0
                
                # Pre-render Progress Bar
                i_bar_class = "bg-success" if i_prog >= 100 else "bg-info"
                i_prog_html = f'''
                    <div class="progress" style="height: 12px; min-width: 80px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated {i_bar_class}" role="progressbar" style="width: {i_prog}%" aria-valuenow="{i_prog}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <small class="text-muted d-block text-center" style="font-size: 0.7rem;">{i_prog}%</small>
                '''

                # Pre-render Rejection
                i_rej = f'<div class="text-danger small mt-1" style="font-size: 0.75rem;">{i_item.rejection_reason}</div>' if i_item.rejection_reason else ''

                i_item.rendered_row_html = mark_safe(f'''
                    <tr class="align-middle">
                        <td><span class="badge bg-light text-dark border">{i_grn.grn_number}</span></td>
                        <td><div class="fw-bold">{i_name}</div></td>
                        <td class="text-center fw-bold text-primary">{i_ordered}</td>
                        <td class="text-center">{i_item.received_quantity}</td>
                        <td class="text-center"><span class="badge bg-success text-white px-2">{i_item.accepted_qty}</span></td>
                        <td class="text-center"><span class="badge bg-danger text-white px-2">{i_item.rejected_qty}</span>{i_rej}</td>
                        <td>{i_prog_html}</td>
                        <td class="small">{i_grn.date_str}</td>
                        <td>{i_grn.user_badge_html}</td>
                    </tr>
                ''')

        indent_data.append({
            "indent": indent,
            "pending_exists": pending_exists,
            "items_data": items_data
        })

    # ---------------------------------------
    # 3️⃣ GROUP PURCHASE ORDERS BY VENDOR
    # ---------------------------------------
    vendor_groups = {}
    for po in pos:
        v_name = po.vendor.name
        if v_name not in vendor_groups:
            vendor_groups[v_name] = {
                'vendor': po.vendor,
                'pos': []
            }
        vendor_groups[v_name]['pos'].append(po)

    # ---------------------------------------
    # RETURN FILTERED DATA
    # ---------------------------------------
    return render(request, "indent/grn_list.html", {
        "vendor_groups": vendor_groups,
        "internal_indents": indent_data,
        "project_id": project_id,
        "department_id": department_id,
    })


@login_required
def create_internal_grn(request, indent_id):
    internal_indent = get_object_or_404(InternalIndent, id=indent_id)

    today_str = timezone.now().strftime("%y%m%d")
    last_grn = GRN.objects.filter(grn_number__startswith=f"XPIGRN{today_str}") \
                          .order_by("id").last()
    last_number = int(last_grn.grn_number[-3:]) if last_grn else 0
    auto_grn_number = f"XPIGRN{today_str}{last_number + 1:03d}"

    pending_items = []

    for item in internal_indent.items.all():
        total_accepted = sum(
            grn_item.accepted_qty
            for igrn in internal_indent.internal_grns.all()
            for grn_item in igrn.items.filter(internal_indent_item=item)
        )
        remaining = item.quantity - total_accepted
        if remaining > 0:
            pending_items.append({
                "id": item.id,
                "name": item.item_name,
                "requested": item.quantity,
                "received": total_accepted,
                "pending": remaining,
            })

    if request.method == "GET" and not pending_items:
        messages.error(request, "All items in this Internal Indent are already received.")
        return redirect("grn_list")

    if request.method == "POST":
        with transaction.atomic():

            grn = GRN.objects.create(
                internal_indent=internal_indent,
                grn_number=auto_grn_number,
                received_date=request.POST.get("received_date"),
                created_by=request.user,
                attachment=request.FILES.get("attachment"),
                grn_type="internal",
            )

            for item in pending_items:
                received_qty = int(request.POST.get(f"received_qty_{item['id']}", 0))

                if received_qty > 0:
                    indent_item = internal_indent.items.get(id=item["id"])
                    pending = item["pending"]

                    accepted_for_indent = min(received_qty, pending)
                    extra_qty = max(received_qty - pending, 0)

                    if accepted_for_indent > 0:
                        GRNItem.objects.create(
                            grn=grn,
                            internal_indent_item=indent_item,
                            received_quantity=accepted_for_indent,
                            accepted_qty=accepted_for_indent,
                            rejected_qty=0,
                            rejection_reason="",
                        )

                    if extra_qty > 0:
                        stock_item, created = StockItem.objects.get_or_create(
                            product_name=indent_item.item_name,
                            defaults={"quantity": 0}
                        )
                        stock_item.quantity += extra_qty
                        stock_item.save()

        # messages.success(request, f"Internal GRN {auto_grn_number} created!")
        return redirect(f"/indent/grn/?project_id={internal_indent.project.id}")

    return render(request, "indent/create_internal_grn.html", {
        "indent": internal_indent,
        "auto_grn_number": auto_grn_number,
        "pending_items": pending_items,
    })


@login_required
def issue_internal_requirement(request, item_id):
    item = get_object_or_404(InternalIndentItem, pk=item_id)
    project = item.internal_indent.project
    
    # Find matching stock item by product_name
    stock_item = StockItem.objects.filter(product_name=item.item_name).first()
    if not stock_item:
        messages.error(request, f"❌ No stock item found matching '{item.item_name}'")
        return redirect("project_detail", pk=project.id)
        
    # Calculate accepted qty (GRNs + direct issues)
    accepted_qty = sum(
        grn_item.accepted_qty
        for igrn in item.internal_indent.internal_grns.all()
        for grn_item in igrn.items.filter(internal_indent_item=item)
    )
    direct_issued_qty = MaterialIssue.objects.filter(internal_indent_item=item).aggregate(total=models.Sum("issued_qty"))["total"] or 0
    total_accepted = accepted_qty + direct_issued_qty
    pending_qty = max(item.quantity - total_accepted, 0)
    
    default_qty = min(pending_qty, stock_item.quantity)
    
    # Find last price
    last_price = 0
    last_grn_item = GRNItem.objects.filter(
        purchase_item__product_name=item.item_name
    ).order_by('-grn__received_date').first()
    if last_grn_item and last_grn_item.purchase_item:
        last_price = last_grn_item.purchase_item.unit_price
    
    if request.method == "POST":
        try:
            issue_qty = int(request.POST.get("issued_qty", default_qty))
        except ValueError:
            issue_qty = 0
            
        try:
            unit_price = Decimal(request.POST.get("unit_price", str(last_price or 0)))
        except (ValueError, TypeError):
            unit_price = Decimal("0.00")
        
        if issue_qty <= 0:
            messages.error(request, "❌ Quantity to issue must be greater than zero.")
            return redirect("issue_internal_requirement", item_id=item.id)
            
        if issue_qty > stock_item.quantity:
            messages.error(request, f"❌ Insufficient stock. Available: {stock_item.quantity}")
            return redirect("issue_internal_requirement", item_id=item.id)
            
        with transaction.atomic():
            stock_item.quantity -= issue_qty
            stock_item.save()
            
            StockLog.objects.create(
                stock_item=stock_item,
                change_quantity=-issue_qty,
                transaction_type='ISSUE',
                description=f"Direct Issue of Production Item: {item.item_name} to Project #{project.id} - {project.name}",
                user=request.user
            )
            
            MaterialIssue.objects.create(
                project=project,
                stock_item=stock_item,
                issued_qty=issue_qty,
                unit_price=unit_price,
                issued_by=request.user,
                internal_indent_item=item
            )
        
        messages.success(request, f"✅ Successfully issued {issue_qty} units of {item.item_name} directly to project from stock.")
        return redirect("project_detail", pk=project.id)
        
    return render(request, "indent/issue_internal_requirement.html", {
        "item": item,
        "project": project,
        "stock_item": stock_item,
        "pending_qty": pending_qty,
        "default_qty": default_qty,
        "last_price": float(last_price)
    })


@login_required
def project_financial_dashboard(request, project_id):
    project = get_object_or_404(Project, pk=project_id)
    allocated_budget = project.revenue or Decimal("0.00")
    
    # 1. Fetch Purchase Orders and compute metrics
    pos = list(PurchaseOrder.objects.filter(indent__project=project).select_related('vendor'))
    today = timezone.now().date()
    
    committed_po = Decimal("0.00")
    total_paid_po = Decimal("0.00")
    total_pending_po = Decimal("0.00")
    overdue_amount = Decimal("0.00")
    overdue_count = 0
    
    po_list_data = []
    for po in pos:
        total_val = po.get_grand_total()
        balance = total_val - po.amount_paid
        committed_po += total_val
        total_paid_po += po.amount_paid
        total_pending_po += balance
        
        is_overdue = False
        if po.due_date and po.due_date < today and po.payment_status != 'paid':
            is_overdue = True
            overdue_amount += balance
            overdue_count += 1
            
        po_list_data.append({
            'po': po,
            'total_val': total_val,
            'balance': balance,
            'is_overdue': is_overdue
        })
        
    # 2. Fetch Direct Material Issues and compute cost
    material_issues = MaterialIssue.objects.filter(project=project).select_related('stock_item', 'issued_by')
    direct_issues_cost = Decimal("0.00")
    for issue in material_issues:
        direct_issues_cost += Decimal(str(issue.issued_qty)) * Decimal(str(issue.unit_price))
        
    total_used = committed_po + direct_issues_cost
    remaining_budget = allocated_budget - total_used
    
    # 3. Kitting calculations
    kit = project.machine_kit
    kit_components_data = []
    total_kit_est_cost = Decimal("0.00")
    total_kit_shortage_cost = Decimal("0.00")
    
    if kit:
        components = kit.components.all().select_related('stock_item', 'department')
        for comp in components:
            # Determine unit price from VendorStock or fallback to last GRNItem
            unit_price = Decimal("0.00")
            v_stock = VendorStock.objects.filter(stock_item=comp.stock_item).first()
            if v_stock and v_stock.price:
                unit_price = Decimal(str(v_stock.price))
            else:
                last_grn = GRNItem.objects.filter(
                    purchase_item__product_name=comp.stock_item.product_name
                ).order_by('-grn__received_date').first()
                if last_grn and last_grn.purchase_item:
                    unit_price = Decimal(str(last_grn.purchase_item.unit_price))
                    
            comp_est_cost = Decimal(str(comp.required_quantity)) * unit_price
            total_kit_est_cost += comp_est_cost
            
            in_stock = Decimal(str(comp.stock_item.quantity))
            req_qty = Decimal(str(comp.required_quantity))
            shortage = max(req_qty - in_stock, Decimal("0.00"))
            comp_shortage_cost = shortage * unit_price
            total_kit_shortage_cost += comp_shortage_cost
            
            kit_components_data.append({
                'component': comp,
                'unit_price': unit_price,
                'est_cost': comp_est_cost,
                'in_stock': in_stock,
                'shortage': shortage,
                'shortage_cost': comp_shortage_cost
            })
            
    # Calculate progress percentages
    used_percent = round((total_used / allocated_budget) * 100, 1) if allocated_budget > 0 else 0
    po_percent = round((committed_po / allocated_budget) * 100, 1) if allocated_budget > 0 else 0
    issue_percent = round((direct_issues_cost / allocated_budget) * 100, 1) if allocated_budget > 0 else 0
    paid_percent = round((total_paid_po / committed_po) * 100, 1) if committed_po > 0 else 0
    
    # Progress bars context helper
    budget_exceeded = total_used > allocated_budget
    over_budget_amount = total_used - allocated_budget if budget_exceeded else Decimal("0.00")
    
    context = {
        'project': project,
        'allocated_budget': allocated_budget,
        'committed_po': committed_po,
        'total_paid_po': total_paid_po,
        'total_pending_po': total_pending_po,
        'direct_issues_cost': direct_issues_cost,
        'total_used': total_used,
        'remaining_budget': remaining_budget,
        'overdue_amount': overdue_amount,
        'overdue_count': overdue_count,
        'po_list_data': po_list_data,
        'material_issues': material_issues,
        'kit': kit,
        'kit_components_data': kit_components_data,
        'total_kit_est_cost': total_kit_est_cost,
        'total_kit_shortage_cost': total_kit_shortage_cost,
        'used_percent': used_percent,
        'po_percent': po_percent,
        'issue_percent': issue_percent,
        'paid_percent': paid_percent,
        'budget_exceeded': budget_exceeded,
        'over_budget_amount': over_budget_amount,
    }
    return render(request, "indent/project_financial_dashboard.html", context)


#  
from django.http import JsonResponse
from .models import StockItem

def product_lookup(request, code):
    try:
        stock = StockItem.objects.get(product_code=code)
        data = {
            "product_code": stock.product_code,
            "product_name": stock.product_name,
            "quantity": stock.quantity,
            "updated_at": stock.updated_at.strftime("%Y-%m-%d %H:%M"),
            "barcode_image": stock.barcode_image.url if stock.barcode_image else None,
        }
        return JsonResponse(data)
    except StockItem.DoesNotExist:
        return JsonResponse({"error": "Product not found"}, status=404)
    

from django.shortcuts import render, get_object_or_404

def product_detail(request, code):
    stock = get_object_or_404(StockItem, product_code=code)
    return render(request, "indent/product_detail.html", {"stock": stock})




from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Enquiry, ProductionOrder, Indent
from django.utils import timezone

def production_orders(request):
    """List all Production Orders and allow creating new ones from confirmed enquiries"""
    pos = ProductionOrder.objects.select_related("enquiry").all()
    confirmed_enquiries = Enquiry.objects.filter(status="confirmed")

    return render(request, "indent/production_orders.html", {
        "pos": pos,
        "confirmed_enquiries": confirmed_enquiries,
    })


def create_production_order(request):
    """Create a Production Order from a confirmed Enquiry"""
    if request.method == "POST":
        enquiry_id = request.POST.get("enquiry_id")
        enquiry = get_object_or_404(Enquiry, id=enquiry_id, status="confirmed")

        po = ProductionOrder.objects.create(
            enquiry=enquiry,
            created_at=timezone.now(),
            status="open"
        )
        return redirect("production_orders")


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from .models import ProductionOrder, Indent
import json

@csrf_exempt
def create_indent(request, po_id):
    """Raise an Indent via AJAX for a specific Production Order"""
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)
    
    try:
        data = json.loads(request.body)
        department = data.get("department", "General")  # default to General
        item = data.get("item", "General")
        qty = int(data.get("qty", 1))
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({"error": "Invalid JSON data"}, status=400)

    po = get_object_or_404(ProductionOrder, id=po_id)

    indent = Indent.objects.create(
        production_order=po,
        title=item,
        quantity=qty,
        requested_by=department,
        department=department,
        status="draft"
    )

    return JsonResponse({
        "success": True,
        "indent_id": indent.id,
        "production_order_id": po.id,
        "department": department,
        "status": indent.status
    })

from .models import Department

def production_orders(request):
    orders = ProductionOrder.objects.select_related("enquiry").all().order_by("-id")
    enquiries = Enquiry.objects.filter(status="confirmed")
    boms = BOM.objects.all()
    indents = Indent.objects.select_related("production_order", "department").all()
    departments = Department.objects.all()

    return render(request, "indent/production_orders.html", {
        "orders": orders,
        "enquiries": enquiries,
        "boms": boms,
        "indents": indents,
        "departments": departments,
    })


@csrf_exempt
def create_production_order(request):
    if request.method == "POST":
        data = json.loads(request.body)
        enquiry_id = data.get("enquiry_id")
        bom_id = data.get("bom_id")

        enquiry = get_object_or_404(Enquiry, id=enquiry_id)
        bom = get_object_or_404(BOM, id=bom_id)

        order = ProductionOrder.objects.create(
            enquiry=enquiry,
            bom=bom,
            status="planning"  # default
        )
        return JsonResponse({"success": True, "id": order.id})
    return JsonResponse({"success": False}, status=400)


@csrf_exempt
def update_production_status(request, order_id):
    if request.method == "POST":
        data = json.loads(request.body)
        status = data.get("status")
        order = get_object_or_404(ProductionOrder, id=order_id)
        order.status = status
        order.save()
        return JsonResponse({"success": True, "status": order.get_status_display()})
    return JsonResponse({"success": False}, status=400)



from django.shortcuts import render, redirect, get_object_or_404
from .models import ProductionOrder, ProductionOrderItem, Snag
from django.contrib.auth.decorators import login_required


@login_required
def production_order_list(request):
    orders = ProductionOrder.objects.all().order_by("-created_at")
    return render(request, "indent/production_order_list.html", {"orders": orders})

@login_required
def production_order_create(request):
    if request.method == "POST":
        enquiry_id = request.POST.get("enquiry_id")
        product_id = request.POST.get("product_id")  # <-- add this

        enquiry = Enquiry.objects.get(pk=enquiry_id)
        product = Products.objects.get(pk=product_id)  # <-- fetch product safely

        order_number = request.POST.get("order_number")
        sales_order = request.POST.get("sales_order")
        planned_start = request.POST.get("planned_start")
        planned_end = request.POST.get("planned_end")

        po = ProductionOrder.objects.create(
            enquiry=enquiry,
            product=product,  # <-- save product
            order_number=order_number,
            sales_order=sales_order,
            created_by=request.user,
            planned_start=planned_start,
            planned_end=planned_end,
        )
        return redirect("production_order_detail", pk=po.pk)

    return render(request, "indent/production_order_form.html", {
        "enquiries": Enquiry.objects.all(),
        "products": Products.objects.all(),  # <-- pass to template
    })


@login_required
def production_order_detail(request, pk):
    po = get_object_or_404(ProductionOrder, pk=pk)

    # related data
    issues = MaterialIssue.objects.filter(production_order=po)
    qc_checks = QCCheck.objects.filter(production_order=po)
    snags = Snag.objects.filter(production_order=po)
    delivery = getattr(po, "delivery", None)

    # forms (bind POST data if exists, otherwise initial)
    issue_form = MaterialIssueForm(request.POST or None, initial={"production_order": po})
    qc_form = QCCheckForm(request.POST or None, initial={"production_order": po, "passed": True})
    delivery_form = DeliveryForm(request.POST or None, initial={"production_order": po})
    snag_form = SnagInlineForm(request.POST or None)

    # flag for inline QC fail section
    qc_fail_trigger_modal = False

    # Auto-pass QC if all associated snags resolved
    unresolved_snags = Snag.objects.filter(production_order=po, resolved=False)
    for qc in qc_checks.filter(passed=False):
        if not unresolved_snags.exists():
            qc.passed = True
            qc.save()

    # Handle POST submissions
    if request.method == "POST":
        if "issue_material" in request.POST:
            if issue_form.is_valid():
                issue = issue_form.save(commit=False)
                issue.production_order = po
                issue.issued_by = request.user
                stock_item = issue_form.cleaned_data["stock_item"]
                qty = issue_form.cleaned_data["issued_qty"]
                if stock_item.quantity < qty:
                    messages.error(request, f"Not enough stock for {stock_item}. Available: {stock_item.quantity}")
                else:
                    stock_item.quantity -= qty
                    stock_item.save()
                    issue.save()
                    # messages.success(request, f"Issued {qty} of {stock_item}.")
                return redirect("production_order_detail", pk=pk)

        elif "qc_check" in request.POST:
            if qc_form.is_valid():
                qc = qc_form.save(commit=False)
                qc.production_order = po
                qc.checked_by = request.user

                if not qc.passed:
                    qc_fail_trigger_modal = True
                    # Validate Snag form
                    if not snag_form.is_valid() or not snag_form.cleaned_data.get('snap_type') or not snag_form.cleaned_data.get('description'):
                        messages.error(request, "QC failed. Snap Type and Reject Reason are required.")
                        # Do NOT redirect — keep the page with inline form
                    else:
                        snag = snag_form.save(commit=False)
                        snag.production_order = po
                        snag.reported_by = request.user
                        snag.save()
                        messages.error(request, f"QC failed. Snag reported: {snag.get_snap_type_display()}")
                        # Do NOT redirect — show inline Snag form

                # else:
                    # messages.success(request, "QC passed successfully!")

                qc.save()
                # Redirect only if QC passed
                if qc.passed:
                    return redirect("production_order_detail", pk=pk)

        elif "delivery" in request.POST:
            if delivery_form.is_valid():
                delivery = delivery_form.save(commit=False)
                delivery.production_order = po
                delivery.save()
                # messages.success(request, "Delivery marked.")
                return redirect("production_order_detail", pk=pk)

    # Build context
    context = {
        "po": po,
        "issues": issues,
        "qc_checks": qc_checks,
        "snags": snags,
        "delivery": delivery,
        "issue_form": issue_form,
        "qc_form": qc_form,
        "delivery_form": delivery_form,
        "snag_form": snag_form,
        "qc_fail_trigger_modal": qc_fail_trigger_modal,
        "machine_kits": MachineKit.objects.all(),
    }
    return render(request, "indent/production_order_detail.html", context)

from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from .models import Indent, IndentItem, StockItem, MaterialIssue, PurchaseOrder, PurchaseItem

def process_indent(request, indent_id):
    indent = get_object_or_404(Indent, id=indent_id)
    indent_items = indent.indentitem_set.all()

    # Only managers should process (pseudo-check)
    if not request.user.groups.filter(name="Manager").exists():
        messages.error(request, " You are not authorized to process indents.")
        return redirect("indent_detail", indent_id=indent.id)

    purchase_order = None
    issue = MaterialIssue.objects.create(
        indent=indent,
        production_order=indent.production_order,
        issued_by=request.user
    )

    for item in indent_items:
        stock_item = StockItem.objects.filter(product_name=item.product_name).first()
        if stock_item and stock_item.available_quantity >= item.quantity:
            # ✅ Enough stock → Issue directly
            stock_item.available_quantity -= item.quantity
            stock_item.save()

            issue.issued_items.create(product_name=item.product_name, quantity=item.quantity)

        else:
            # ❌ Shortfall → Create Purchase Order
            required_qty = item.quantity
            available_qty = stock_item.available_quantity if stock_item else 0
            shortage = required_qty - available_qty

            # Issue whatever is available
            if available_qty > 0 and stock_item:
                stock_item.available_quantity = 0
                stock_item.save()
                issue.issued_items.create(product_name=item.product_name, quantity=available_qty)

            # Create purchase order for remaining
            if not purchase_order:
                purchase_order = PurchaseOrder.objects.create(
                    vendor=None,  # TODO: Assign vendor selection logic
                    po_number=f"PO-{indent.id}",
                    created_by=request.user,
                    remarks="Auto-generated from Indent shortage",
                    payment_terms='Credit'  # Ensure default even in auto-creation
                )

            PurchaseItem.objects.create(
                purchase_order=purchase_order,
                product_name=item.product_name,
                quantity=shortage,
                unit_price=0  # TODO: Vendor pricing
            )

    indent.status = "processed"
    indent.save()

    # messages.success(request, " Indent processed successfully.")
    return redirect("indent_detail", indent_id=indent.id)


@login_required
def indent_detail(request, pk):
    indent = get_object_or_404(Indent.objects.prefetch_related("items"), pk=pk)
    return render(request, "indent/indent_detail.html", {"indent": indent})

@login_required
def material_issue_create(request, production_order_id):
    production_order = get_object_or_404(ProductionOrder, pk=production_order_id)

    if request.method == "POST":
        form = MaterialIssueForm(request.POST)
        if form.is_valid():
            issue = form.save(commit=False)
            issue.production_order = production_order
            issue.issued_by = request.user

            # get stock item and issued quantity from form
            stock_item = form.cleaned_data["stock_item"]
            issued_qty = form.cleaned_data["issued_qty"]   # ✅ correct field

            # check stock availability
            stock = get_object_or_404(StockItem, pk=stock_item.id)
            if stock.quantity < issued_qty:
                messages.error(
                    request,
                    f"Not enough stock for {stock_item}. Available: {stock.quantity}"
                )
                return redirect("material_issue_create", production_order_id=production_order.id)

            # reduce stock
            stock.quantity -= issued_qty
            stock.save()

            StockLog.objects.create(
                stock_item=stock,
                change_quantity=-issued_qty,
                transaction_type='ISSUE',
                description=f"Issued to PO #{production_order.id}",
                user=request.user
            )

            # save issue
            issue.issued_qty = issued_qty
            issue.save()

            # messages.success(
            #     request,
            #     f"Issued {issued_qty} units of {stock_item} and updated stock."
            # )
            return redirect("production_order_detail", production_order.id)
    else:
        form = MaterialIssueForm(initial={"production_order": production_order})

    return render(request, "indent/material_issue_form.html", {
        "form": form,
        "production_order": production_order,
        "production_orders": ProductionOrder.objects.all(),
        "stock_items": StockItem.objects.all(),
    })


@login_required
def qc_check_create(request, production_order_id):
    production_order = get_object_or_404(ProductionOrder, pk=production_order_id)

    if request.method == "POST":
        form = QCCheckForm(request.POST)
        if form.is_valid():
            qc_check = form.save(commit=False)
            qc_check.production_order = production_order
            qc_check.save()

            # if qc_check.passed:   # ✅ use passed
            #     messages.success(request, "QC Passed ✅")
            # else:
            #     messages.error(request, "QC Failed ❌")

            return redirect("production_order_detail", production_order.id)
    else:
        form = QCCheckForm()

    return render(request, "indent/qc_check_form.html", {
        "form": form,
        "production_order": production_order,
    })


@login_required
def telemetry_list(request, production_order_id):
    production_order = get_object_or_404(ProductionOrder, pk=production_order_id)
    records = TelemetryRecord.objects.filter(production_order=production_order).order_by("-recorded_at")
    return render(request, "indent/telemetry_list.html", {
        "production_order": production_order,
        "records": records
    })


@login_required
def project_material_issue(request, project_id):
    """Issue material from stock to a project"""
    print(f"🔍 DEBUG: project_material_issue called with project_id={project_id}, method={request.method}")
    project = get_object_or_404(Project, pk=project_id)
    print(f"🔍 DEBUG: Found project: {project.name}")

    if request.method == "POST":
        print(f"🔍 DEBUG: Processing POST request")
        form = MaterialIssueForm(request.POST)
        print(f"🔍 DEBUG: Form created, is_valid={form.is_valid()}")
        
        if form.is_valid():
            print(f"🔍 DEBUG: Form is valid, processing...")
            issue = form.save(commit=False)
            issue.project = project
            issue.production_order = None  # Explicitly set to None
            issue.issued_by = request.user

            # get stock item, issued quantity, and unit price from form
            stock_item = form.cleaned_data["stock_item"]
            issued_qty = form.cleaned_data["issued_qty"]
            unit_price = form.cleaned_data["unit_price"]
            print(f"🔍 DEBUG: Stock item: {stock_item}, Quantity: {issued_qty}, Unit Price: {unit_price}")

            # check stock availability
            stock = get_object_or_404(StockItem, pk=stock_item.id)
            print(f"🔍 DEBUG: Current stock quantity: {stock.quantity}")
            
            if stock.quantity < issued_qty:
                print(f"🔍 DEBUG: Insufficient stock, redirecting...")
                messages.error(
                    request,
                    f"❌ Not enough stock for {stock_item}. Available: {stock.quantity}"
                )
                return redirect("project_material_issue", project_id=project.id)

            # reduce stock
            stock.quantity -= issued_qty
            stock.save()
            print(f"🔍 DEBUG: Stock reduced to {stock.quantity}")

            StockLog.objects.create(
                stock_item=stock,
                change_quantity=-issued_qty,
                transaction_type='ISSUE',
                description=f"Issued to Project #{project.id} - {project.name}",
                user=request.user
            )
            print(f"🔍 DEBUG: StockLog created")

            # save issue
            issue.issued_qty = issued_qty
            issue.unit_price = unit_price
            issue.save()
            print(f"🔍 DEBUG: MaterialIssue saved with ID: {issue.id}")

            messages.success(
                request,
                f"✅ Successfully issued {issued_qty} units of {stock_item.product_name} @ ₹{unit_price}/unit to {project.name}. Total value: ₹{issued_qty * unit_price}"
            )
            print(f"🔍 DEBUG: Redirecting to project_detail with pk={project.id}")
            return redirect("project_detail", pk=project.id)
        else:
            # Form validation failed
            print(f"🔍 DEBUG: Form validation FAILED. Errors: {form.errors}")
            messages.error(
                request,
                f"❌ Form validation failed. Please check your inputs. Errors: {form.errors}"
            )
    else:
        print(f"🔍 DEBUG: GET request, creating empty form")
        form = MaterialIssueForm()
    
    # Get stock items with their last purchase prices
    stock_items_with_prices = []
    for stock in StockItem.objects.all():
        # Try to get last purchase price from GRN items
        last_grn_item = GRNItem.objects.filter(
            purchase_item__product_name=stock.product_name
        ).order_by('-grn__received_date').first()
        
        last_price = 0
        if last_grn_item and last_grn_item.purchase_item:
            last_price = last_grn_item.purchase_item.unit_price
        
        stock_items_with_prices.append({
            'id': stock.id,
            'name': stock.product_name,
            'quantity': stock.quantity,
            'last_price': float(last_price)
        })

    print(f"🔍 DEBUG: Rendering template")
    return render(request, "indent/project_material_issue.html", {
        "form": form,
        "project": project,
        "stock_items": StockItem.objects.all(),
        "stock_items_with_prices": json.dumps(stock_items_with_prices),
    })


@login_required
def delivery_create(request, production_order_id):
    production_order = get_object_or_404(ProductionOrder, pk=production_order_id)

    if request.method == "POST":
        form = DeliveryForm(request.POST)
        if form.is_valid():
            delivery = form.save(commit=False)
            delivery.production_order = production_order
            delivery.created_by = request.user
            delivery.save()

            # Update status
            production_order.status = "Delivered"
            production_order.save()

            # Optionally: trigger invoice
            # Invoice.objects.create(
            #     production_order=production_order,
            #     delivery=delivery,
            #     created_by=request.user
            # )

            # messages.success(request, "Delivery note generated and linked to invoice.")
            return redirect("production_order_detail", production_order.id)
    else:
        form = DeliveryForm()

    return render(request, "indent/delivery_form.html", {
        "form": form,
        "production_order": production_order
    })

#  
from django.http import JsonResponse

@login_required
def get_stock_quantity(request, stock_id):
    stock = get_object_or_404(StockItem, pk=stock_id)
    return JsonResponse({"quantity": stock.quantity})


from django.http import JsonResponse

@login_required
def resolve_snag(request, snag_id):
    snag = get_object_or_404(Snag, id=snag_id)
    snag.resolved = True
    snag.save()

    # Auto-pass QC if all snags resolved for the production order
    po = snag.production_order
    unresolved_snags = Snag.objects.filter(production_order=po, resolved=False)
    if not unresolved_snags.exists():
        for qc in QCCheck.objects.filter(production_order=po, passed=False):
            qc.passed = True
            qc.save()

    return JsonResponse({"success": True})


# /mnt/data/ 

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from .models import Project, Department, MachineKit
from .forms import ProjectForm

@login_required
def project_list(request):
    if request.user.is_superuser or request.user.is_staff or request.user.groups.filter(name='Production').exists():
        projects_qs = Project.objects.all().order_by("-id")
    else:
        projects_qs = Project.objects.filter(assigned_users=request.user).distinct().order_by("-id")

    projects = []

    for p in projects_qs:
        g_requested = 0
        g_accepted = 0

        # Internal Progress
        internal_sum = InternalIndentItem.objects.filter(
            internal_indent__project=p
        ).aggregate(total=models.Sum("quantity"))["total"] or 0
        
        internal_accepted = (
            GRNItem.objects.filter(grn__internal_indent__project=p).aggregate(total=models.Sum("accepted_qty"))["total"] or 0
        ) + (
            MaterialIssue.objects.filter(internal_indent_item__internal_indent__project=p).aggregate(total=models.Sum("issued_qty"))["total"] or 0
        )
        
        g_requested += internal_sum
        g_accepted += internal_accepted

        # Purchase Progress
        purchase_sum = IndentItem.objects.filter(
            indent__project=p
        ).aggregate(total=models.Sum("quantity"))["total"] or 0
        
        purchase_accepted = GRNItem.objects.filter(
            purchase_item__po__indent__project=p
        ).aggregate(total=models.Sum("accepted_qty"))["total"] or 0
        
        g_requested += purchase_sum
        g_accepted += purchase_accepted

        if g_requested > 0:
            prog = round((g_accepted / g_requested) * 100, 1)
        else:
            prog = 0
        
        color = "bg-success" if prog >= 100 else "bg-primary"
        p.progress_html = mark_safe(f'''
            <div class="d-flex align-items-center gap-2" style="min-width: 100px;">
                <div class="progress flex-grow-1" style="height: 8px;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated {color}" role="progressbar" style="width: {prog}%"></div>
                </div>
                <small class="fw-bold">{prog}%</small>
            </div>
        ''')
        projects.append(p)

    form = ProjectForm()
    is_production = request.user.groups.filter(name='Production').exists()
    is_admin = request.user.is_superuser or request.user.is_staff
    
    from Riva.models import Enquiry
    import json
    confirmed_enquiries = Enquiry.objects.filter(is_confirmed=True).exclude(oc_number__isnull=True).exclude(oc_number__exact='')
    oc_to_enq_id = {enq.oc_number: enq.id for enq in confirmed_enquiries}
    oc_to_enq_id_json = json.dumps(oc_to_enq_id)
    
    return render(request, "indent/projects.html", {
        "projects": projects,
        "form": form,
        "is_production": is_production,
        "is_admin": is_admin,
        "oc_to_enq_id_json": oc_to_enq_id_json,
    })

@login_required
@permission_required('indent.can_create_project', raise_exception=True)
def project_create_ajax(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()
            form.save_m2m()  # Important for saving ManyToMany fields
            return JsonResponse({"success": True})
        return JsonResponse({"success": False, "errors": form.errors})
    return JsonResponse({"success": False})


@login_required
def project_edit_ajax(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if request.method == "GET":
        return JsonResponse({
            "id": project.id,
            "name": project.name,
            "place": project.place,
            "requirement": project.requirement,
            "configuration": project.configuration,
            "revenue": project.revenue,
            "project_type": project.project_type,
            "oc_number": project.oc_number,
            "plan_start": project.plan_start,
            "plan_end": project.plan_end,
            "delivery_date": project.delivery_date,
            "status": project.status,
            "lead": project.lead_id if project.lead else "",
            "machine_kit": project.machine_kit_id if project.machine_kit else "",
            "assigned_users": list(project.assigned_users.values_list('id', flat=True)),
            "product": project.product_id if project.product else "",
        })

    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            return JsonResponse({"success": True})
        return JsonResponse({"success": False, "errors": form.errors})


#   (add or replace project_detail and optionally add delete view)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import InternalIndent, InternalIndentItem, Indent  # Indent exists already
from .models import Department, Project  # adjust import paths if models live elsewhere
from django.db import transaction

@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)

    is_admin = request.user.is_superuser or request.user.is_staff
    is_production = request.user.groups.filter(name='Production').exists()
    is_stock = request.user.groups.filter(name='Stock').exists()

    if not (is_admin or is_production):
        if not project.assigned_users.filter(id=request.user.id).exists():
            from django.contrib import messages
            messages.error(request, "You are not assigned to this project.")
            return redirect('project_list')

    if is_admin or is_stock or is_production:
        departments = Department.objects.all()
    else:
        is_lead = False
        if project.lead and project.lead.assigned_users.filter(id=request.user.id).exists():
            is_lead = True
        
        if is_lead:
            departments = Department.objects.all()
        else:
            departments = Department.objects.filter(assigned_users=request.user).distinct()

    if request.method == "POST":
        dept_id = request.POST.get("dept_id")
        dept = get_object_or_404(Department, id=dept_id)

        item_ids = request.POST.getlist("item_id[]")
        names = request.POST.getlist("item_name[]")
        qtys = request.POST.getlist("quantity[]")
        dues = request.POST.getlist("due_date[]")

        # DELETE CHECKBOX VALUES
        delete_ids = request.POST.getlist("delete_item[]")

        # ✅ CLEAN delete_ids — remove blanks and non-numbers
        delete_ids = [d for d in delete_ids if d.strip().isdigit()]

        # Fetch or create internal indent
        internal_indent = InternalIndent.objects.filter(project=project, department=dept).first()
        if not internal_indent:
            today = timezone.now().strftime("%y%m%d")
            last = InternalIndent.objects.filter(indent_number__startswith=f"XPINT{today}").order_by("id").last()
            last_no = int(last.indent_number[-3:]) if last else 0
            new_no = f"XPINT{today}{last_no + 1:03d}"

            internal_indent = InternalIndent.objects.create(
                project=project,
                department=dept,
                indent_number=new_no,
                created_by=request.user,
                status="internal"
            )

        with transaction.atomic():
            # ✅ DELETE SELECTED ITEMS FIRST
            delete_ids = [d for d in delete_ids if d.strip().isdigit()]

            if delete_ids:
                InternalIndentItem.objects.filter(id__in=delete_ids,
                                                internal_indent=internal_indent).delete()

            # PROCESS ROWS
            for idx, name in enumerate(names):
                name = (name or "").strip()
                if not name:
                    continue

                # 🛑 VALIDATE: Check if item exists in StockItem
                if not StockItem.objects.filter(product_name__iexact=name).exists():
                    messages.error(request, f"Error: Item '{name}' does not exist in Stock. Please add it to Stock first.")
                    return redirect("project_detail", pk=pk)

                qty_raw = qtys[idx] if idx < len(qtys) else "1"
                due_raw = dues[idx] if idx < len(dues) else None

                qty = int(qty_raw) if qty_raw.isdigit() else 1
                item_id = item_ids[idx].strip() if idx < len(item_ids) else ""

                if item_id.isdigit():
                    # UPDATE
                    try:
                        item = InternalIndentItem.objects.get(id=item_id, internal_indent=internal_indent)
                        item.item_name = name
                        item.quantity = qty
                        item.due_date = due_raw or None
                        item.save()
                    except InternalIndentItem.DoesNotExist:
                        InternalIndentItem.objects.create(
                            internal_indent=internal_indent,
                            item_name=name,
                            quantity=qty,
                            due_date=due_raw or None
                        )
                else:
                    # CREATE NEW
                    InternalIndentItem.objects.create(
                        internal_indent=internal_indent,
                        item_name=name,
                        quantity=qty,
                        due_date=due_raw or None
                    )

        # messages.success(request, f"Internal requirement updated for {dept.name}.")
        return redirect("project_detail", pk=pk)

    # GET request
    dept_data = []
    grand_total_requested = 0
    grand_total_accepted = 0

    for dept in departments:
        indent = InternalIndent.objects.filter(project=project, department=dept).first()
        items = []
        indent_prog_html = ""
        
        if indent:
            # Map of accepted quantities for items in this indent
            accepted_map = {}
            grn_items = GRNItem.objects.filter(
                grn__internal_indent=indent
            ).values("internal_indent_item_id").annotate(total=models.Sum("accepted_qty"))
            
            for g_item in grn_items:
                accepted_map[g_item["internal_indent_item_id"]] = g_item["total"]

            # Also add direct material issues satisfying these requirements
            direct_issues = MaterialIssue.objects.filter(
                internal_indent_item__internal_indent=indent
            ).values("internal_indent_item_id").annotate(total=models.Sum("issued_qty"))
            
            for d_issue in direct_issues:
                item_id = d_issue["internal_indent_item_id"]
                accepted_map[item_id] = accepted_map.get(item_id, 0) + d_issue["total"]

            total_requested = 0
            total_accepted = 0

            # Prefetch StockItem quantity to avoid N+1 queries
            item_names = [i.item_name for i in indent.items.all()]
            stock_map = {}
            for s in StockItem.objects.filter(product_name__in=item_names):
                stock_map[s.product_name.lower()] = s.quantity

            for item in indent.items.select_related('requested_by_dept').all():
                accepted = accepted_map.get(item.id, 0)
                item.accepted_qty = accepted
                item.pending_qty = max(item.quantity - accepted, 0)
                item.stock_qty = stock_map.get(item.item_name.lower(), 0)
                
                # Calculate item-level progress
                if item.quantity > 0:
                    prog = round((accepted / item.quantity) * 100, 1)
                else:
                    prog = 0
                
                # Item Progress Bar (Internal Helper style)
                bar_class = "bg-success" if prog >= 100 else "bg-info"
                item.progress_html = mark_safe(f'''
                    <div class="progress" style="height: 6px; width: 100px;">
                        <div class="progress-bar progress-bar-striped progress-bar-animated {bar_class}" role="progressbar" style="width: {prog}%" aria-valuenow="{prog}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                ''')
                item.progress_percent = prog
                
                items.append(item)
                total_requested += item.quantity
                total_accepted += accepted

            grand_total_requested += total_requested
            grand_total_accepted += total_accepted

            # Indent level progress
            if total_requested > 0:
                indent_prog = round((total_accepted / total_requested) * 100, 1)
            else:
                indent_prog = 0
            
            indent_bar_class = "bg-success" if indent_prog >= 100 else "bg-primary"
            indent_prog_html = mark_safe(f'''
                <div class="d-flex align-items-center gap-2">
                    <div class="progress flex-grow-1" style="height: 12px; min-width: 120px;">
                        <div class="progress-bar {indent_bar_class} progress-bar-striped progress-bar-animated" role="progressbar" style="width: {indent_prog}%" aria-valuenow="{indent_prog}" aria-valuemin="0" aria-valuemax="100"></div>
                    </div>
                    <span class="fw-bold text-dark" style="font-size: 0.85rem;">{indent_prog}%</span>
                </div>
            ''')

        dept_data.append({
            "dept": dept,
            "indent": indent,
            "items": items,
            "has_items": bool(items),
            "indent_prog_html": indent_prog_html,
        })

    if is_admin or is_stock or is_production:
        raw_indents = Indent.objects.filter(project=project).select_related("department")
    else:
        raw_indents = Indent.objects.filter(project=project, department__in=departments).select_related("department")
    project_indents = []
    
    for pi in raw_indents:
        # Calculate progress for this Purchase Indent
        total_p_ordered = 0
        total_p_accepted = 0
        
        items_qs = IndentItem.objects.filter(indent=pi)
        for i_item in items_qs:
            total_p_ordered += i_item.quantity
            
            # Accepted qty from GRN
            accepted = GRNItem.objects.filter(
                purchase_item__po__indent=pi,
                purchase_item__product_name=i_item.product_name
            ).aggregate(total=models.Sum("accepted_qty"))["total"] or 0
            
            total_p_accepted += accepted

        grand_total_requested += total_p_ordered
        grand_total_accepted += total_p_accepted

        if total_p_ordered > 0:
            p_prog = round((total_p_accepted / total_p_ordered) * 100, 1)
        else:
            p_prog = 0
            
        p_bar_class = "bg-success" if p_prog >= 100 else "bg-info"
        pi.progress_html = mark_safe(f'''
            <div class="d-flex align-items-center gap-2">
                <div class="progress flex-grow-1" style="height: 8px; min-width: 100px;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated {p_bar_class}" role="progressbar" style="width: {p_prog}%" aria-valuenow="{p_prog}" aria-valuemin="0" aria-valuemax="100"></div>
                </div>
                <small class="fw-bold">{p_prog}%</small>
            </div>
        ''')
        project_indents.append(pi)

    # Calculate Overall Project Progress
    if grand_total_requested > 0:
        overall_prog = round((grand_total_accepted / grand_total_requested) * 100, 1)
    else:
        overall_prog = 0
    
    overall_color = "bg-success" if overall_prog >= 100 else "bg-primary"
    project.progress_html = mark_safe(f'''
        <div class="card bg-white p-3 border rounded shadow-sm mb-4">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <span class="fw-bold text-uppercase text-muted small">Overall Project Fulfillment</span>
                <span class="badge bg-dark fs-6">{overall_prog}%</span>
            </div>
            <div class="progress" style="height: 20px;">
                <div class="progress-bar progress-bar-striped progress-bar-animated {overall_color}" role="progressbar" style="width: {overall_prog}%" aria-valuenow="{overall_prog}" aria-valuemin="0" aria-valuemax="100"></div>
            </div>

        </div>
    ''')

    today_str = timezone.now().strftime("%y%m%d")
    stock_dict = {}
    for d in departments:
        dept_code = None
        dept_name_upper = d.name.strip().upper()
        dept_code_upper = (d.code or "").strip().upper()
        
        # 1. Match by choice key directly (e.g. name is "MSF", choice key is "MSF")
        for key, display in StockItem.DEPARTMENTS:
            if dept_name_upper == key.upper() or dept_code_upper == key.upper():
                dept_code = key
                break
        
        if not dept_code:
            # 2. Match by choice display name (e.g. name is "REACTOR ASSEMBLY FLOOR", choice display is "REACTOR ASSEMBLY FLOOR")
            for key, display in StockItem.DEPARTMENTS:
                if dept_name_upper == display.strip().upper() or dept_code_upper == display.strip().upper():
                    dept_code = key
                    break
        
        if not dept_code:
            # 3. Substring matching
            for key, display in StockItem.DEPARTMENTS:
                if key.upper() in dept_name_upper or dept_name_upper in key.upper():
                    dept_code = key
                    break
                if display.strip().upper() in dept_name_upper or dept_name_upper in display.strip().upper():
                    dept_code = key
                    break
        
        if not dept_code:
            dept_code = d.code or d.name
            
        matched_stock = StockItem.objects.filter(
            stock_type__in=['semifinished', 'finished'],
            department=dept_code
        )
        stock_dict[str(d.id)] = {s.product_name: (s.quantity or 0) for s in matched_stock}
        
    import json
    stock_json = json.dumps(stock_dict)

    # Fetch issued materials for this project
    issued_materials = MaterialIssue.objects.filter(project=project).select_related('stock_item', 'issued_by').order_by('-issued_at')

    # Additional groups checking
    is_vendor = request.user.groups.filter(name='Vendor').exists()
    is_grn = request.user.groups.filter(name='GRN').exists()
    is_accounts = request.user.groups.filter(name='Accounts').exists()

    return render(request, "indent/project_detail.html", {
        "project": project,
        "dept_data": dept_data,
        "project_indents": project_indents,
        "stock_json": stock_json,
        "issued_materials": issued_materials,
        "is_admin": is_admin,
        "is_production": is_production,
        "is_stock": is_stock,
        "is_vendor": is_vendor,
        "is_grn": is_grn,
        "is_accounts": is_accounts,
    })

# Optional: simple view to delete a single internal item (if you want a dedicated endpoint)
@login_required
def internal_item_delete(request, pk):
    item = get_object_or_404(InternalIndentItem, pk=pk)
    project_pk = item.internal_indent.project.pk
    if request.method == "POST":
        item.delete()
        # messages.success(request, "Item deleted.")
    return redirect("project_detail", pk=project_pk)


@login_required
def project_indent_create(request, project_id, dept_id):

    project = get_object_or_404(Project, id=project_id)
    department = get_object_or_404(Department, id=dept_id)
    stock_items = StockItem.objects.all()

    today_str = timezone.now().strftime("%y%m%d")
    last_indent = Indent.objects.filter(indent_number__startswith=f"XPIND{today_str}").order_by('id').last()

    if last_indent:
        last_number = int(last_indent.indent_number[-3:])
    else:
        last_number = 0

    next_indent_number = f"XPIND{today_str}{last_number + 1:03d}"

    if request.method == "POST":
        title = request.POST.get("title")
        description = request.POST.get("description", "")
        department_id = request.POST.get("department")
        department = get_object_or_404(Department, id=department_id)

        required_date = request.POST.get("required_date")
        if not required_date:
            required_date = None

        indent = Indent.objects.create(
            title=title,
            remarks=description,
            status="draft",
            created_by=request.user,
            indent_number=next_indent_number,
            department=department,
            project=project,   # 🔥 IMPORTANT
            required_date=required_date,
        )

        item_names = request.POST.getlist("item_name[]")
        quantities = request.POST.getlist("quantity[]")
        units = request.POST.getlist("unit[]")
        production_items = request.POST.getlist("production_item[]")

        for i in range(len(item_names)):
            name = item_names[i].strip()
            qty = quantities[i]
            unit = units[i]
            sfg_id = production_items[i] if i < len(production_items) else None

            if name and qty:
                stock = StockItem.objects.filter(product_name__iexact=name).first()
                if not stock:
                    messages.error(request, f"Error: Item '{name}' does not exist in Stock. Please use a valid stock item.")
                    return redirect(f"{reverse('indent_list')}?project={project.id}")

                code = stock.product_code
                
                sfg = None
                if sfg_id and sfg_id.isdigit():
                    sfg = InternalIndentItem.objects.filter(id=sfg_id).first()

                IndentItem.objects.create(
                    indent=indent,
                    product_code=code,
                    product_name=name,
                    quantity=int(qty),
                    unit=unit,
                    production_item=sfg
                )

        # messages.success(request, f"Indent {indent.indent_number} created successfully!")
        from_deployment = request.GET.get("from_deployment")
        if from_deployment:
            deployment = Deployment.objects.filter(project=project).first()
            if deployment:
                return redirect("deployment_details", deployment_id=deployment.id)
        return redirect(f"{reverse('indent_list')}?project={project.id}")

    # 👉 Handle GET request: Filter SFGs for this project and department
    internal_indent = InternalIndent.objects.filter(project=project, department=department).first()
    sfg_items = []
    if internal_indent:
        raw_sfg_items = list(internal_indent.items.all())
        item_names = [i.item_name for i in raw_sfg_items]
        stock_map = {}
        for s in StockItem.objects.filter(product_name__in=item_names):
            stock_map[s.product_name.lower()] = s.quantity
        for sfg in raw_sfg_items:
            sfg.stock_qty = stock_map.get(sfg.item_name.lower(), 0)
            sfg_items.append(sfg)

    departments = Department.objects.all()

    # Prepare stock JSON grouped by department
    stock_dict = {}
    for d in departments:
        dept_code = None
        dept_name_upper = d.name.strip().upper()
        dept_code_upper = (d.code or "").strip().upper()
        
        # 1. Match by choice key directly
        for key, display in StockItem.DEPARTMENTS:
            if dept_name_upper == key.upper() or dept_code_upper == key.upper():
                dept_code = key
                break
        
        if not dept_code:
            # 2. Match by choice display name
            for key, display in StockItem.DEPARTMENTS:
                if dept_name_upper == display.strip().upper() or dept_code_upper == display.strip().upper():
                    dept_code = key
                    break
        
        if not dept_code:
            # 3. Substring matching
            for key, display in StockItem.DEPARTMENTS:
                if key.upper() in dept_name_upper or dept_name_upper in key.upper():
                    dept_code = key
                    break
                if display.strip().upper() in dept_name_upper or dept_name_upper in display.strip().upper():
                    dept_code = key
                    break
        
        if not dept_code:
            dept_code = d.code or d.name
            
        matched_stock = StockItem.objects.filter(
            department=dept_code
        )
        stock_dict[str(d.id)] = {s.product_name: (s.quantity or 0) for s in matched_stock}
        
    import json
    stock_json = json.dumps(stock_dict)

    return render(request, "indent/indent_form.html", {
        "stock_items": stock_items,
        "next_indent_number": next_indent_number,
        "selected_department": department,
        "selected_project": project,
        "default_indent_title": project.name,
        "departments": departments,
        "is_project_indent": True,
        "sfg_items": sfg_items,  # 🔥 PASS SFGs TO TEMPLATE
        "stock_json": stock_json,
    })


@login_required
def project_department_indents(request, project_id, dept_id):
    project = get_object_or_404(Project, id=project_id)
    department = get_object_or_404(Department, id=dept_id)
    indents = project.project_indents.filter(department=department)
    return render(request, "indent/project_department_indents.html", {
        "project": project,
        "department": department,
        "indents": indents,
    })


@login_required
def indent_details(request, indent_id):
    indent = get_object_or_404(Indent, id=indent_id)
    items = indent.items.all()

    # Add stock availability
    for item in items:
        stock = StockItem.objects.filter(product_name=item.product_name).first()
        item.stock_available = stock.quantity if stock else 0
        item.shortage = max(item.quantity - item.stock_available, 0)

    vendors = Vendor.objects.all()

    # Group approved purchase items BY vendor
    vendor_groups = {}
    for item in items:
        if (
            item.approved and
            item.source_type == "purchase" and
            item.vendor and
            item.shortage_qty > 0
        ):
            vendor_name = item.vendor.name
            if vendor_name not in vendor_groups:
                # Check for existing non-rejected PO
                existing_po = PurchaseOrder.objects.filter(indent=indent, vendor=item.vendor).exclude(status='rejected').first()
                vendor_groups[vendor_name] = {
                    'items': [],
                    'existing_po': existing_po,
                    'vendor_id': item.vendor.id
                }
            vendor_groups[vendor_name]['items'].append(item)

    is_admin = request.user.is_superuser or request.user.is_staff
    is_accounts = request.user.groups.filter(name='Accounts').exists()
    is_stock = request.user.groups.filter(name='Stock').exists()
    is_vendor = request.user.groups.filter(name='Vendor').exists()

    return render(request, "indent/indent_details.html", {
        "indent": indent,
        "items": items,
        "vendors": vendors,
        "vendor_groups": vendor_groups,
        "is_admin": is_admin,
        "is_accounts": is_accounts,
        "is_stock": is_stock,
        "is_vendor": is_vendor,
    })




@login_required
def update_indent_item(request, item_id):
    item = get_object_or_404(IndentItem, id=item_id)

    if request.method == "POST":
        action = request.POST.get("action")

        # ---------------- SUBMIT ----------------
        if action == "submit":
            stock_to_use = int(request.POST.get("stock_to_use", 0))
            shortage_qty = int(request.POST.get("shortage_qty", 0))
            vendor_id = request.POST.get("vendor")
            remarks = request.POST.get("remarks", "")

            if shortage_qty > 0 and not vendor_id:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({"success": False, "error": "Please select a vendor before submitting shortage items."})
                messages.error(request, "Please select a vendor before submitting shortage items.")
                return redirect("indent_details", indent_id=item.indent.id)

            item.stock_to_use = stock_to_use
            item.shortage_qty = shortage_qty
            item.remarks = remarks
            if vendor_id:
                item.vendor_id = vendor_id
            else:
                item.vendor = None
            item.submitted = True
            item.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                vendor_name = item.vendor.name if item.vendor else "-"
                return JsonResponse({
                    "success": True, 
                    "stock_to_use": item.stock_to_use,
                    "shortage_qty": item.shortage_qty,
                    "vendor": vendor_name,
                    "remarks": item.remarks or "-"
                })
            return redirect("indent_details", indent_id=item.indent.id)

        # ---------------- REJECT ----------------
        if action == "reject":
            reason = request.POST.get("reject_reason")

            if not reason:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({"success": False, "error": "Reject reason is required."})
                messages.error(request, "Reject reason is required.")
                return redirect("indent_details", indent_id=item.indent.id)

            item.approved = False
            item.rejected = True
            item.submitted = True  # Keep it submitted so it shows rejected status
            item.source_type = ""
            item.vendor = None
            item.shortage_qty = 0
            item.reject_reason = reason
            item.save()

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"success": True, "rejected": True})
            return redirect("indent_details", indent_id=item.indent.id)

        # ---------------- APPROVE ----------------
        if action == "approve":
            stock_to_use = int(request.POST.get("stock_to_use", item.stock_to_use or 0))
            shortage_qty = int(request.POST.get("shortage_qty", item.shortage_qty or 0))
            unit_price = float(request.POST.get("unit_price", item.unit_price or 0.0))
            vendor_id = request.POST.get("vendor") or (item.vendor.id if item.vendor else None)
            remarks = request.POST.get("remarks", item.remarks or "")

            if shortage_qty > 0 and not vendor_id:
                messages.error(request, "Please select a vendor before approving.")
                return redirect("indent_details", indent_id=item.indent.id)

            item.approved = True
            item.rejected = False
            item.stock_to_use = stock_to_use
            item.shortage_qty = shortage_qty
            item.unit_price = unit_price
            item.remarks = remarks
            
            if vendor_id:
                item.vendor_id = vendor_id
            else:
                item.vendor = None
            
            # Stock management
            stock = StockItem.objects.filter(product_name=item.product_name).first()
            if stock:
                # Use the EXPLICIT stock_to_use value provided by the user
                if stock_to_use > 0:
                    stock.quantity = max(stock.quantity - stock_to_use, 0)
                    stock.save()
                    
                # Auto-generate remark if empty and we have a split
                if not remarks and stock_to_use > 0 and shortage_qty > 0:
                    item.remarks = f"Used {stock_to_use} from stock, remaining {shortage_qty} planned for purchase."

            item.save()
            
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({"success": True, "approved": True})
            return redirect("indent_details", indent_id=item.indent.id)

@login_required
def email_log_list(request):
    logs = EmailLog.objects.select_related('purchase_order').all().order_by('-timestamp')
    whatsapp_logs = WhatsAppLog.objects.select_related("purchase_order").order_by("-sent_at")
    
    po_id = request.GET.get('po_id')
    if po_id:
        logs = logs.filter(purchase_order_id=po_id)
        whatsapp_logs = whatsapp_logs.filter(purchase_order_id=po_id)
        
    return render(request, 'indent/email_log_list.html', {
        'logs': logs,
        'whatsapp_logs': whatsapp_logs
    })

@login_required
def sfg_stock_search(request):
    q = request.GET.get("q", "")
    stocks = StockItem.objects.filter(
        product_name__icontains=q, 
        stock_type__in=["semifinished", "finished"]
    )[:10]
    results = [{"name": s.product_name, "quantity": s.quantity} for s in stocks]
    return JsonResponse(results, safe=False)


@login_required
def create_cross_dept_request(request, project_id):
    if request.method == "POST":
        project = get_object_or_404(Project, id=project_id)
        target_dept_id = request.POST.get("target_dept")
        requesting_dept_id = request.POST.get("requesting_dept")
        
        target_dept = get_object_or_404(Department, id=target_dept_id)
        requesting_dept = get_object_or_404(Department, id=requesting_dept_id)

        # Batch items
        item_names = request.POST.getlist("item_name[]")
        quantities = request.POST.getlist("quantity[]")
        due_dates = request.POST.getlist("due_date[]")

        # Fallback for single item (if any remains)
        if not item_names:
            it_name = request.POST.get("item_name")
            if it_name:
                item_names = [it_name]
                quantities = [request.POST.get("quantity", 1)]
                due_dates = [request.POST.get("due_date")]

        if not item_names:
             messages.warning(request, "No items were requested.")
             return redirect("project_detail", pk=project_id)

        # Get or create InternalIndent for target dept
        internal_indent = InternalIndent.objects.filter(project=project, department=target_dept).first()
        if not internal_indent:
            today = timezone.now().strftime("%y%m%d")
            last = InternalIndent.objects.filter(indent_number__startswith=f"XPINT{today}").order_by("id").last()
            last_no = int(last.indent_number[-3:]) if last else 0
            new_no = f"XPINT{today}{last_no + 1:03d}"

            internal_indent = InternalIndent.objects.create(
                project=project,
                department=target_dept,
                indent_number=new_no,
                created_by=request.user,
                status="internal"
            )

        count = 0
        for name, qty, due in zip(item_names, quantities, due_dates):
            name = name.strip()
            if name and qty:
                # 🛑 VALIDATE: Check if item exists in Stock
                if not StockItem.objects.filter(product_name__iexact=name).exists():
                    messages.error(request, f"Error: Item '{name}' does not exist in stock. Please select a valid item.")
                    return redirect("project_detail", pk=project_id)

                InternalIndentItem.objects.create(
                    internal_indent=internal_indent,
                    item_name=name,
                    quantity=int(qty),
                    due_date=due if due else None,
                    requested_by_dept=requesting_dept
                )
                count += 1
        
        if count > 0:
            messages.success(request, f"{count} request(s) sent to {target_dept.name}.")
        
        return redirect("project_detail", pk=project_id)

    return redirect("project_list")

@login_required
def sync_vendor_ratings(request):
    """Manually trigger a recalculation of all automated vendor ratings."""
    from .models import Vendor
    vendors = Vendor.objects.all()
    count = 0
    for vendor in vendors:
        vendor.update_automated_ratings()
        count += 1
    
    messages.success(request, f"Successfully recalculated automated ratings for {count} vendors.")
    return redirect("vendor_list")



@login_required
def project_combined_po_print(request, project_id, vendor_id):
    """
    Shows a unified print view for all approved/pending POs for a specific vendor in a project.
    No new records are created.
    """
    project = get_object_or_404(Project, id=project_id)
    vendor = get_object_or_404(Vendor, pk=vendor_id)
    
    # Fetch all approved or pending POs for this project and vendor
    pos = PurchaseOrder.objects.filter(
        vendor=vendor,
        indent__project=project,
        status__in=['approved', 'pending']
    )
    
    if not pos.exists():
        messages.warning(request, "No approved or pending Purchase Orders found for this vendor in this project.")
        return redirect('project_detail', pk=project_id)
    
    combined_items = []
    total_amount = 0
    for po in pos:
        for item in po.items.all():
            combined_items.append(item)
            total_amount += (item.quantity or 0) * (item.unit_price or 0)
            
    company = {
        "name": "Xpredict Automation Solutions Pvt Ltd",
        "address": "Thimlapura Road, Hurulichikanahalli, Bengaluru 560090",
        "phone": "7795625583",
        "email": "info@xpredictlabs.com",
        "gst": "29AAACX2581L1ZU",
        "pan": "AAACX2581L",
        "logo": "static/xlogo.jpeg"
    }
    
    # Create a mock PO object for the template
    mock_po = {
        "po_number": f"COMBINED-{project.id}-{vendor.code or vendor.id}",
        "created_at": timezone.now(),
        "total_amount": total_amount
    }
    
    return render(request, "indent/po_print.html", {
        "po": mock_po,
        "items": combined_items,
        "company": company,
        "total_amount": total_amount,
        "vendor": vendor,
    })

@login_required
def check_project_vendors_for_print(request, project_id):
    """
    Finds vendors who already have approved/pending POs in this project.
    """
    project = get_object_or_404(Project, id=project_id)
    vendor_ids = PurchaseOrder.objects.filter(
        indent__project=project,
        status__in=['approved', 'pending']
    ).values_list('vendor', flat=True).distinct()
    
    vendors = Vendor.objects.filter(id__in=vendor_ids).values('id', 'name', 'code')
    return JsonResponse({"vendors": list(vendors)})
@login_required
def project_material_issue_from_indent(request, project_id, indent_id=None):
    """Issue materials from an indent to a project"""
    project = get_object_or_404(Project, pk=project_id)
    
    # If no indent_id, show indent selection page
    if not indent_id:
        indents = Indent.objects.filter(project=project).order_by('-created_at')
        return render(request, "indent/select_indent_for_issue.html", {
            "project": project,
            "indents": indents,
        })
    
    # Get the selected indent
    indent = get_object_or_404(Indent, pk=indent_id, project=project)
    
    if request.method == "POST":
        # Process multiple items
        items_data = []
        errors = []
        
        # Parse form data for each item
        for key in request.POST:
            if key.startswith('selected_'):
                item_id = key.replace('selected_', '')
                if request.POST.get(key) == 'on':
                    try:
                        indent_item = IndentItem.objects.get(pk=item_id)
                        qty = int(request.POST.get(f'qty_{item_id}', 0))
                        price = float(request.POST.get(f'price_{item_id}', 0))
                        
                        if qty <= 0:
                            errors.append(f"Invalid quantity for {indent_item.product_name}")
                            continue
                        
                        # Find matching stock item
                        stock = StockItem.objects.filter(product_name=indent_item.product_name).first()
                        if not stock:
                            errors.append(f"No stock found for {indent_item.product_name}")
                            continue
                        
                        if stock.quantity < qty:
                            errors.append(f"Insufficient stock for {indent_item.product_name}. Available: {stock.quantity}, Requested: {qty}")
                            continue
                        
                        items_data.append({
                            'indent_item': indent_item,
                            'stock': stock,
                            'qty': qty,
                            'price': price,
                        })
                    except (IndentItem.DoesNotExist, ValueError) as e:
                        errors.append(f"Error processing item: {str(e)}")
        
        if errors:
            for error in errors:
                messages.error(request, f"❌ {error}")
        
        if items_data and not errors:
            # Issue all items
            total_value = 0
            issued_count = 0
            
            for item_data in items_data:
                indent_item = item_data['indent_item']
                stock = item_data['stock']
                qty = item_data['qty']
                price = item_data['price']
                
                # Reduce stock
                stock.quantity -= qty
                stock.save()
                
                # Update issued quantity on indent item
                indent_item.issued_qty += qty
                indent_item.save()
                
                # Create stock log
                StockLog.objects.create(
                    stock_item=stock,
                    change_quantity=-qty,
                    transaction_type='ISSUE',
                    description=f"Issued to Project #{project.id} - {project.name} (from Indent #{indent.indent_number})",
                    user=request.user
                )
                
                # Create material issue
                MaterialIssue.objects.create(
                    project=project,
                    stock_item=stock,
                    issued_qty=qty,
                    unit_price=price,
                    issued_by=request.user
                )
                
                total_value += qty * price
                issued_count += 1
            
            messages.success(
                request,
                f"✅ Successfully issued {issued_count} items from Indent #{indent.indent_number} to {project.name}. Total value: ₹{total_value:.2f}"
            )
            return redirect("project_detail", pk=project.id)
        elif not items_data:
            messages.warning(request, "⚠️ No items selected for issuance")
    
    # GET request - show indent items
    indent_items_data = []
    print(f"🔍 DEBUG: Indent {indent.indent_number} has {indent.items.count()} items")
    
    for item in indent.items.all():
        print(f"🔍 DEBUG: Processing item: {item.product_name}, qty: {item.quantity}, issued: {item.issued_qty}")
        
        # Calculate remaining quantity to issue
        remaining_qty = item.quantity - item.issued_qty
        
        # Skip fully issued items
        if remaining_qty <= 0:
            print(f"🔍 DEBUG: Skipping {item.product_name} - fully issued")
            continue
        
        # Find matching stock
        stock = StockItem.objects.filter(product_name=item.product_name).first()
        print(f"🔍 DEBUG: Found stock: {stock}, available: {stock.quantity if stock else 0}")
        
        # Get last purchase price
        last_price = 0
        if stock:
            last_grn_item = GRNItem.objects.filter(
                purchase_item__product_name=item.product_name
            ).order_by('-grn__received_date').first()
            
            if last_grn_item and last_grn_item.purchase_item:
                last_price = float(last_grn_item.purchase_item.unit_price)
        
        item_data = {
            'indent_item': item,
            'stock': stock,
            'available_qty': stock.quantity if stock else 0,
            'requested_qty': remaining_qty,  # Show remaining qty instead of original
            'issued_qty': item.issued_qty,
            'total_qty': item.quantity,
            'last_price': last_price,
            'has_stock': stock is not None,
            'sufficient_stock': stock and stock.quantity >= remaining_qty if stock else False,
        }
        
        print(f"🔍 DEBUG: Item data dict: {item_data}")
        print(f"🔍 DEBUG: - indent_item.id: {item.id}")
        print(f"🔍 DEBUG: - indent_item.product_name: {item.product_name}")
        print(f"🔍 DEBUG: - requested_qty (remaining): {remaining_qty}")
        print(f"🔍 DEBUG: - issued_qty: {item.issued_qty}")
        print(f"🔍 DEBUG: - available_qty: {stock.quantity if stock else 0}")
        print(f"🔍 DEBUG: - last_price: {last_price}")
        
        indent_items_data.append(item_data)
    
    print(f"🔍 DEBUG: Total indent_items_data: {len(indent_items_data)}")
    print(f"🔍 DEBUG: Context data - project: {project}, indent: {indent}")
    
    return render(request, "indent/project_material_issue_from_indent.html", {
        "project": project,
        "indent": indent,
        "indent_items_data": indent_items_data,
    })
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
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

            # Also add direct material issues satisfying these requirements
            direct_issues = MaterialIssue.objects.filter(
                internal_indent_item__internal_indent=indent
            ).aggregate(total=models.Sum("issued_qty"))["total"] or 0
            total_accepted += direct_issues
            
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
            
    # Calculate lead department progress based on non-lead departments
    non_lead_progs = [n["progress"] for n in nodes if not n["is_lead"]]
    avg_prog = 0
    if non_lead_progs:
        avg_prog = round(sum(non_lead_progs) / len(non_lead_progs), 1)
        
    for node in nodes:
        if node["is_lead"]:
            node["progress"] = avg_prog

    has_loading_photos = False
    has_documents = False
    if hasattr(project, 'deployment'):
        has_loading_photos = project.deployment.images.filter(image_type='loading').exists()
        has_documents = project.deployment.documents.exists()

    return render(request, "indent/project_assembly.html", {
        "project": project,
        "nodes": nodes,
        "is_deployed": hasattr(project, 'deployment'),
        "has_loading_photos": has_loading_photos,
        "has_documents": has_documents,
    })

def client_project_assembly(request, token):
    project = get_object_or_404(Project, client_token=token)
    
    if project.status == 'completed':
        return render(request, "indent/client_link_expired.html", {"project": project})
        
    departments = Department.objects.all()
    
    nodes = []
    
    for dept in departments:
        indent = InternalIndent.objects.filter(project=project, department=dept).first()
        prog = 0
        has_tasks = False
        
        if indent:
            has_tasks = True
            total_requested = 0
            for item in indent.items.all():
                total_requested += item.quantity
                
            grn_items = GRNItem.objects.filter(
                grn__internal_indent=indent
            ).values("internal_indent_item_id").annotate(total=models.Sum("accepted_qty"))
            
            total_accepted = sum([g["total"] for g in grn_items if g["total"]])

            # Also add direct material issues satisfying these requirements
            direct_issues = MaterialIssue.objects.filter(
                internal_indent_item__internal_indent=indent
            ).aggregate(total=models.Sum("issued_qty"))["total"] or 0
            total_accepted += direct_issues
            
            if total_requested > 0:
                prog = round((total_accepted / total_requested) * 100, 1)
            else:
                prog = 100
                
        is_lead = (project.lead and dept.id == project.lead.id)
        if has_tasks or is_lead:
            nodes.append({
                "id": dept.id,
                "name": dept.name,
                "progress": min(prog, 100),
                "is_lead": is_lead
            })
            
    non_lead_progs = [n["progress"] for n in nodes if not n["is_lead"]]
    avg_prog = 0
    if non_lead_progs:
        avg_prog = round(sum(non_lead_progs) / len(non_lead_progs), 1)
        
    for node in nodes:
        if node["is_lead"]:
            node["progress"] = avg_prog

    has_loading_photos = False
    has_documents = False
    if hasattr(project, 'deployment'):
        has_loading_photos = project.deployment.images.filter(image_type='loading').exists()
        has_documents = project.deployment.documents.exists()

    return render(request, "indent/client_project_assembly.html", {
        "project": project,
        "nodes": nodes,
        "is_deployed": hasattr(project, 'deployment'),
        "has_loading_photos": has_loading_photos,
        "has_documents": has_documents,
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
            
            # Fetch all SFGs for this project (InternalIndentItem objects for this project's InternalIndents)
            sfgs = InternalIndentItem.objects.filter(internal_indent__project=project)
            for sfg in sfgs:
                raw_materials = IndentItem.objects.filter(production_item=sfg)
                
                # If an SFG has no materials, we can skip or show 0%
                if not raw_materials.exists():
                    continue
                    
                items_data = []
                sfg_requested = 0
                sfg_issued = 0
                
                for rm in raw_materials:
                    requested = rm.quantity
                    issued = rm.issued_qty
                    
                    sfg_requested += requested
                    sfg_issued += issued
                    
                    items_data.append({
                        "item_name": rm.product_name,
                        "requested": requested,
                        "accepted": issued,
                    })
                
                prog = round((sfg_issued / sfg_requested) * 100, 1) if sfg_requested > 0 else 100
                
                snapshot_data.append({
                    "id": sfg.id,
                    "name": sfg.item_name,
                    "progress": min(prog, 100),
                    "items": items_data
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
            img_type = request.POST.get('image_type', 'loading')
            if files:
                for f in files:
                    DeploymentImage.objects.create(deployment=deployment, image=f, image_type=img_type)
                messages.success(request, f"{len(files)} {img_type} image(s) uploaded successfully.")
            else:
                messages.error(request, "Please select at least one image file.")
            return redirect(f"{reverse('deployment_details', args=[deployment.id])}#{img_type}")
            
        elif 'delete_image' in request.POST:
            img_id = request.POST.get('image_id')
            img = get_object_or_404(DeploymentImage, pk=img_id, deployment=deployment)
            img.delete()
            messages.success(request, "Image deleted successfully.")
            # Determine which tab to return to based on image type
            back_to = request.POST.get('back_to', 'loading')
            return redirect(f"{reverse('deployment_details', args=[deployment.id])}#{back_to}")

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
        
        elif 'complete_project' in request.POST:
            project.status = 'completed'
            project.save()
            messages.success(request, f"Project {project.name} has been marked as Completed.")
            return redirect(reverse('deployment_details', args=[deployment.id]))
        
    documents_grouped = {}
    for choice in DeploymentDocument.DOCUMENT_TYPES:
        doc_key = choice[0]
        doc_name = choice[1]
        documents_grouped[doc_name] = {
            'key': doc_key,
            'files': deployment.documents.filter(document_type=doc_key).order_by('-uploaded_at')
        }
        
    # Generate live nested snapshot of ALL department requirements + GRN Status
    snapshot_data = []
    from django.db.models import Sum
    from indent.models import Department, InternalIndentItem, IndentItem, GRNItem
    
    # Only show departments that actually have requirements for this project
    active_dept_ids = set()
    active_dept_ids.update(Indent.objects.filter(project=project).values_list('department_id', flat=True))
    active_dept_ids.update(InternalIndent.objects.filter(project=project).values_list('department_id', flat=True))
    
    departments = Department.objects.filter(id__in=[d for d in active_dept_ids if d])
    
    for dept in departments:
        requirements_data = []
        dept_requested = 0
        dept_issued = 0
        dept_received = 0
        
        # 1. Process Internal Indents (SFGs / Assembly Requirements)
        dept_sfgs = InternalIndentItem.objects.filter(
            internal_indent__project=project, 
            internal_indent__department=dept
        ).select_related('internal_indent')
        
        for sfg in dept_sfgs:
            raw_materials = IndentItem.objects.filter(production_item=sfg).select_related('indent')
            items_data = []
            sfg_requested = 0
            sfg_issued = 0
            sfg_received = 0
            
            for rm in raw_materials:
                # Calculate GRN received quantity for this specific material
                # Step 1: Find all purchase items associated with this indent for this project
                relevant_po_items = PurchaseItem.objects.filter(
                    po__indent=rm.indent,
                    product_name=rm.product_name
                )
                
                # Step 2: Sum up accepted quantities from GRNs linked to those PO items
                grn_qty = GRNItem.objects.filter(
                    purchase_item__in=relevant_po_items
                ).aggregate(total=Sum('accepted_qty'))['total'] or 0
                
                items_data.append({
                    "item_name": rm.product_name,
                    "requested": rm.quantity,
                    "received": grn_qty,
                    "accepted": rm.issued_qty, # This is 'Used' quantity
                })
                sfg_requested += rm.quantity
                sfg_issued += rm.issued_qty
                sfg_received += grn_qty
            
            dept_requested += sfg_requested
            dept_issued += sfg_issued
            dept_received += sfg_received
            
            procurement_prog = round((sfg_received / sfg_requested) * 100, 1) if sfg_requested > 0 else 0
            
            requirements_data.append({
                "id": f"sfg_{sfg.id}",
                "name": f"Assembly: {sfg.item_name}",
                "procurement_progress": min(procurement_prog, 100),
                "items": items_data
            })
            
        # 2. Process General Indents (Materials not linked to a specific SFG)
        general_indents = Indent.objects.filter(
            project=project,
            department=dept
        ).prefetch_related('items')
        
        for indent in general_indents:
            unlinked_items = indent.items.filter(production_item__isnull=True)
            if unlinked_items.exists():
                items_data = []
                ind_requested = 0
                ind_received = 0
                for rm in unlinked_items:
                    # Calculate GRN received quantity
                    relevant_po_items = PurchaseItem.objects.filter(
                        po__indent=indent,
                        product_name=rm.product_name
                    )
                    
                    grn_qty = GRNItem.objects.filter(
                        purchase_item__in=relevant_po_items
                    ).aggregate(total=Sum('accepted_qty'))['total'] or 0
                    
                    items_data.append({
                        "item_name": rm.product_name,
                        "requested": rm.quantity,
                        "received": grn_qty,
                    })
                    ind_requested += rm.quantity
                    ind_received += grn_qty
                
                dept_requested += ind_requested
                dept_received += ind_received
                
                proc_prog = round((ind_received / ind_requested) * 100, 1) if ind_requested > 0 else 0
                
                requirements_data.append({
                    "id": f"ind_{indent.id}",
                    "name": f"Requirement: {indent.title or indent.indent_number}",
                    "procurement_progress": min(proc_prog, 100),
                    "items": items_data
                })

        proc_main_prog = round((dept_received / dept_requested) * 100, 1) if dept_requested > 0 else 0
        
        snapshot_data.append({
            "id": dept.id,
            "name": dept.name,
            "procurement_progress": min(proc_main_prog, 100),
            "requirements": requirements_data
        })
        
    departments_all = Department.objects.all().order_by('name')
    context = {
        'deployment': deployment,
        'project': project,
        'image_form': image_form,
        'documents_grouped': documents_grouped,
        'snapshot': snapshot_data,
        'departments_all': departments_all,
        'loading_images': deployment.images.filter(image_type='loading').order_by('-uploaded_at'),
        'unloading_images': deployment.images.filter(image_type='unloading').order_by('-uploaded_at'),
    }
    
    return render(request, "indent/deployment_details.html", context)
@login_required
def vendor_payments_board(request):
    """
    List vendors with outstanding balances.
    """
    # Prepare data for dashboard
    vendor_data = []
    for vendor in Vendor.objects.all():
        total_pending = 0
        unattended_count = 0
        today_date = timezone.now().date()
        
        from django.db.models import Q
        # Show POs that are Approved OR explicitly sent to the vendor
        po_list = PurchaseOrder.objects.filter(
            Q(status='approved') | Q(sent_to_vendor=True),
            vendor=vendor
        ).exclude(payment_status='paid')

        for po in po_list:
            grand_total = po.get_grand_total()
            pending = grand_total - po.amount_paid
            
            # Only include POs that have a non-zero price and pending balance
            if grand_total > 0 and pending > 0:
                total_pending += pending
                # Unattended check: Payment is overdue based on its specific due_date
                if po.due_date < today_date:
                    unattended_count += 1
        
        if total_pending > 0:
            vendor_data.append({
                'vendor': vendor,
                'total_pending': total_pending,
                'unattended_count': unattended_count,
            })

    return render(request, "indent/vendor_payment_board.html", {
        "vendor_data": vendor_data,
    })

@login_required
def vendor_po_payment_checkout(request, vendor_id):
    """
    Handle bulk payment for a vendor's POs.
    """
    vendor = get_object_or_404(Vendor, id=vendor_id)
    # Show POs that are Approved OR explicitly sent to the vendor
    from django.db.models import Q
    unpaid_pos_query = PurchaseOrder.objects.filter(
        Q(status='approved') | Q(sent_to_vendor=True),
        vendor=vendor
    ).exclude(payment_status='paid').order_by('created_at')
    
    unpaid_pos = []
    # Calculate priorities and filter out 0-price POs
    today = timezone.now().date()
    for po in unpaid_pos_query:
        grand_total = po.get_grand_total()
        if grand_total > 0:
            po.remaining_balance = grand_total - po.amount_paid
            # po.due_date is now a property on the model
            po.is_priority = po.due_date <= today
            unpaid_pos.append(po)
    
    if request.method == "POST":
        selected_po_ids = request.POST.getlist('selected_pos')
        transaction_id = request.POST.get('transaction_id')
        proof = request.FILES.get('proof')
        remarks = request.POST.get('remarks')
        
        if not selected_po_ids:
            messages.error(request, "Select at least one PO to pay.")
            return redirect('vendor_po_payment_checkout', vendor_id=vendor.id)
        
        total_payment_amount = Decimal('0.00')
        affected_pos = []
        
        for po_id in selected_po_ids:
            po = get_object_or_404(PurchaseOrder, id=po_id)
            pay_amount_str = request.POST.get(f'pay_amount_{po_id}')
            
            try:
                pay_amount = Decimal(pay_amount_str) if pay_amount_str else Decimal('0.00')
                if pay_amount > 0:
                    po.amount_paid += pay_amount
                    grand_total = po.get_grand_total()
                    
                    if po.amount_paid >= grand_total:
                        po.payment_status = 'paid'
                    else:
                        po.payment_status = 'partial'
                    
                    po.save()
                    total_payment_amount += pay_amount
                    affected_pos.append(po)
            except (ValueError, Exception):
                continue
        
        if total_payment_amount > 0:
            # Create ONE payment log for all selected POs
            payment_log = POPaymentLog.objects.create(
                vendor=vendor,
                amount_paid=total_payment_amount,
                transaction_id=transaction_id,
                payment_proof=proof,
                remarks=remarks
            )
            payment_log.purchase_orders.set(affected_pos)
            
            messages.success(request, f"Successfully recorded ₹{total_payment_amount} for {len(affected_pos)} POs (Ref: {transaction_id}).")
            return redirect('vendor_payments_board')
            
    return render(request, "indent/vendor_payment_checkout.html", {
        "vendor": vendor,
        "unpaid_pos": unpaid_pos,
    })


@login_required
def vendor_payment_history(request, vendor_id):
    """
    Shows the history of all payments made to a specific vendor.
    """
    vendor = get_object_or_404(Vendor, id=vendor_id)
    payment_logs = POPaymentLog.objects.filter(vendor=vendor).prefetch_related('purchase_orders').order_by('-paid_at')
    
    return render(request, "indent/vendor_payment_history.html", {
        'vendor': vendor,
        'payment_logs': payment_logs,
    })

@login_required
def weekly_payment_forecast(request):
    """
    Provides a 7-day outlook of upcoming Purchase Order payments grouped by vendor.
    """
    from datetime import timedelta
    from collections import defaultdict
    from decimal import Decimal
    
    today = timezone.now().date()
    seven_days_later = today + timedelta(days=7)
    
    from django.db.models import Q
    # Fetch all unpaid POs that are Approved OR Sent to Vendor
    unpaid_pos_query = PurchaseOrder.objects.filter(
        Q(status='approved') | Q(sent_to_vendor=True)
    ).exclude(payment_status='paid').select_related('vendor')
    
    # Group results in Python because due_date is dynamic per vendor
    forecast_map = defaultdict(lambda: {'total_due': Decimal('0.00'), 'po_count': 0})
    
    for po in unpaid_pos_query:
        grand_total = po.get_grand_total()
        # Use dynamic due date property from model (handles C&C vs Credit)
        due_date = po.due_date
        
        # Check if it falls within our window (next 7 days)
        if today <= due_date <= seven_days_later:
            remaining = grand_total - po.amount_paid
            if remaining > 0:
                v_id = po.vendor.id
                forecast_map[v_id]['vendor__id'] = v_id
                forecast_map[v_id]['vendor__name'] = po.vendor.name
                forecast_map[v_id]['total_due'] += remaining
                forecast_map[v_id]['po_count'] += 1
    
    # Convert to list and sort by highest due
    vendor_forecast = sorted(forecast_map.values(), key=lambda x: x['total_due'], reverse=True)
    total_weekly_requirement = sum(item['total_due'] for item in vendor_forecast)
    
    return render(request, 'indent/weekly_payment_forecast.html', {
        'forecast': vendor_forecast,
        'total_weekly_requirement': total_weekly_requirement,
        'start_date': today,
        'end_date': seven_days_later
    })

@login_required
def export_vendor_template(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "Vendors"
    headers = [
        "Name", "Code", "Category", "Contact Number", 
        "Contact Number 2", "Contact Email", "GST Number", 
        "PAN Number", "Bank Name", "Bank Account No", 
        "IFSC Code", "Level (L1/L2/L3)", "Credit Period (Days)"
    ]
    ws.append(headers)
    
    # Add Data Validation for Level (Column L)
    dv = DataValidation(type="list", formula1='"L1,L2,L3,L4"', allow_blank=True)
    ws.add_data_validation(dv)
    dv.add("L2:L1000")
    
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = "attachment; filename=vendor_template.xlsx"
    wb.save(response)
    return response

@login_required
def import_vendors(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]
        try:
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            
            created_count = 0
            updated_count = 0
            
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row[0]: continue  
                
                name, code, category, contact, contact2, email, gst, pan, bank, acc, ifsc, level, credit = row[:13]
                
                try:
                    credit_days = int(credit) if credit is not None else 30
                except (ValueError, TypeError):
                    credit_days = 30

                vendor, created = Vendor.objects.update_or_create(
                    name=str(name),
                    defaults={
                        'code': str(code) if code else '',
                        'category': str(category) if category else '',
                        'contact_number': str(contact) if contact else '',
                        'contact_number_2': str(contact2) if contact2 else '',
                        'contact_email': str(email) if email else '',
                        'gst_number': str(gst) if gst else '',
                        'pan_number': str(pan) if pan else '',
                        'bank_name': str(bank) if bank else '',
                        'bank_account_no': str(acc) if acc else '',
                        'ifsc_code': str(ifsc) if ifsc else '',
                        'level': level if level in ['L1', 'L2', 'L3', 'L4'] else 'L1',
                        'credit_period_days': credit_days,
                    }
                )
                if created: created_count += 1
                else: updated_count += 1
                
            messages.success(request, f"Import complete: {created_count} created, {updated_count} updated.")
        except Exception as e:
            messages.error(request, f"Error processing file: {str(e)}")
            
    return redirect('vendor_list')

@login_required
def export_stock_template(request):
    wb = Workbook()
    ws = wb.active
    ws.title = "StockItems"
    headers = [
        "Product Name", "Product Code", "Stock Type", 
        "Department", "Quantity", "Min Stock",
        "Vendor Name (Optional)", "Unit Price (₹)", "Lead Time (Days)"
    ]
    ws.append(headers)
    
    # Add help info for choices in a separate sheet
    ref_ws = wb.create_sheet("Reference")
    ref_ws.append(["Stock Types", "Departments", "Vendors"])
    types = ["capital", "running", "consumables", "finished", "semifinished", "raw"]
    depts = ["RAF", "MSF", "PSF", "WAH", "ESD", "PKG"]
    vendors = list(Vendor.objects.values_list('name', flat=True))
    
    for i in range(max(len(types), len(depts), len(vendors))):
        t = types[i] if i < len(types) else ""
        d = depts[i] if i < len(depts) else ""
        v = vendors[i] if i < len(vendors) else ""
        ref_ws.append([t, d, v])

    # Add Data Validation
    dv_type = DataValidation(type="list", formula1='"capital,running,consumables,finished,semifinished,raw"', allow_blank=True)
    dv_dept = DataValidation(type="list", formula1='"RAF,MSF,PSF,WAH,ESD,PKG"', allow_blank=True)
    
    # For Vendor Name dropdown, we use the Reference sheet
    # In Excel, formulas referring to other sheets need to be quoted if sheet has spaces, but "Reference" is fine.
    # Note: openpyxl formula1 for cross-sheet needs a named range or direct ref 'Reference'!$C$2:$C$1000
    dv_vendor = DataValidation(type="list", formula1=f"Reference!$C$2:$C${len(vendors) + 1 if vendors else 2}", allow_blank=True)
    
    ws.add_data_validation(dv_type)
    ws.add_data_validation(dv_dept)
    ws.add_data_validation(dv_vendor)
    
    dv_type.add("C2:C1000")
    dv_dept.add("D2:D1000")
    dv_vendor.add("G2:G1000")
    
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = "attachment; filename=stock_template.xlsx"
    wb.save(response)
    return response

@login_required
def import_stock(request):
    if request.method == "POST" and request.FILES.get("excel_file"):
        excel_file = request.FILES["excel_file"]
        try:
            wb = openpyxl.load_workbook(excel_file)
            ws = wb.active
            
            created_stock = 0
            updated_stock = 0
            mapped_vendors = 0
            errors = []
            
            for index, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                # More robust row check: skip only if both name and code are missing
                p_name = str(row[0]).strip() if row[0] else None
                p_code = str(row[1]).strip() if row[1] else None
                
                if not p_name and not p_code:
                    continue  
                
                # Extract data (up to 9 columns now)
                # Headers: Name, Code, Type, Dept, Qty, Min, VName, VPrice, VLead
                s_type, dept, qty, min_s = row[2:6]
                v_name = str(row[6]).strip() if len(row) > 6 and row[6] else None
                v_price = row[7] if len(row) > 7 else None
                v_lead = row[8] if len(row) > 8 else None
                
                try:
                    qty_int = int(qty) if qty is not None else 0
                    min_stock_int = int(min_s) if min_s is not None else 0
                except (ValueError, TypeError):
                    qty_int = 0
                    min_stock_int = 0

                lookup = {}
                if p_code:
                    lookup = {'product_code': p_code}
                else:
                    lookup = {'product_name': p_name}
                    
                try:
                    stock, created = StockItem.objects.update_or_create(
                        **lookup,
                        defaults={
                            'product_name': p_name if p_name else (stock.product_name if 'stock' in locals() else 'Unnamed Item'),
                            'product_code': p_code if p_code else '',
                            'stock_type': s_type if s_type in dict(StockItem.STOCK_TYPES) else 'raw',
                            'department': dept if dept in dict(StockItem.DEPARTMENTS) else 'MSF',
                            'quantity': qty_int,
                            'min_stock': min_stock_int,
                        }
                    )
                    if created: created_stock += 1
                    else: updated_stock += 1
                    
                    # Handle Vendor Mapping if provided
                    if v_name:
                        vendor = Vendor.objects.filter(name__iexact=v_name).first()
                        if vendor:
                            try:
                                price_dec = Decimal(str(v_price)) if v_price is not None else Decimal('0.0')
                                lead_int = int(v_lead) if v_lead is not None else 0
                            except (ValueError, TypeError, Exception):
                                price_dec = Decimal('0.0')
                                lead_int = 0
                                
                            VendorStock.objects.update_or_create(
                                stock_item=stock,
                                vendor=vendor,
                                defaults={
                                    'price': price_dec,
                                    'lead_time': lead_int
                                }
                            )
                            mapped_vendors += 1
                        else:
                            errors.append(f"Row {index}: Vendor '{v_name}' not found.")
                            
                except Exception as e:
                    errors.append(f"Row {index}: Error saving {p_name or p_code}: {str(e)}")
                
            msg = f"Import complete: {created_stock} created, {updated_stock} updated."
            if mapped_vendors:
                msg += f" {mapped_vendors} vendor mappings updated."
            messages.success(request, msg)
            
            if errors:
                for err in errors[:5]: # Show first 5 errors
                    messages.warning(request, err)
                if len(errors) > 5:
                    messages.warning(request, f"...and {len(errors)-5} more issues.")
                    
        except Exception as e:
            messages.error(request, f"System error reading file: {str(e)}")
            
    return redirect('stock_list')

@login_required
def manage_permissions(request):
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "You do not have permission to access this page.")
        return redirect('indent_list')

    from django.contrib.auth.models import User, Group
    from django.db.models import Q
    from .models import Department
    
    target_group_names = ['Production', 'Stock', 'GRN', 'Accounts', 'Vendor']
    groups = Group.objects.filter(name__in=target_group_names)
    departments = Department.objects.all()

    if request.method == 'POST':
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'user_id' in request.POST:
            # Single-user AJAX update
            user_id = request.POST.get('user_id')
            is_admin_check = request.POST.get('is_admin') == 'true'
            submitted_group_names = request.POST.getlist('groups') or request.POST.getlist('groups[]')
            submitted_dept_ids = request.POST.getlist('departments') or request.POST.getlist('departments[]')
            
            try:
                user = User.objects.get(id=int(user_id))
            except (ValueError, User.DoesNotExist):
                return JsonResponse({"success": False, "error": "User not found."})
                
            # Prevent lock-out of currently logged-in user
            if user.id == request.user.id and request.user.is_superuser:
                # Force admin to stay admin
                user.is_superuser = True
                user.is_staff = True
            else:
                user.is_superuser = is_admin_check
                user.is_staff = is_admin_check
                
            user.save()
            
            # Clear target groups and re-apply
            user.groups.remove(*groups)
            for g_name in submitted_group_names:
                try:
                    g = Group.objects.get(name=g_name)
                    user.groups.add(g)
                except Group.DoesNotExist:
                    continue
            
            # Update assigned departments
            user.assigned_departments.clear()
            for d_id in submitted_dept_ids:
                try:
                    d = Department.objects.get(id=int(d_id))
                    user.assigned_departments.add(d)
                except (ValueError, Department.DoesNotExist):
                    continue
            
            # Return fresh group names and department IDs for updating UI
            updated_groups = list(user.groups.values_list('name', flat=True))
            updated_depts = list(user.assigned_departments.values_list('id', flat=True))
            return JsonResponse({
                "success": True, 
                "is_admin": user.is_superuser,
                "groups": updated_groups,
                "departments": updated_depts
            })
            
        # Legacy/fallback form post (standard table submission)
        submitted_groups = request.POST.getlist('user_groups')
        submitted_admins = request.POST.getlist('user_admins')
        
        # Clear groups for all users
        all_users = User.objects.all()
        for user in all_users:
            user.groups.remove(*groups)
            
            # Prevent lock-out of the current logged-in user if they are admin
            if user.id == request.user.id and request.user.is_superuser:
                # Force current user to remain admin
                user.is_superuser = True
                user.is_staff = True
            else:
                is_admin_check = str(user.id) in submitted_admins
                user.is_superuser = is_admin_check
                user.is_staff = is_admin_check
            
            user.save()
                
        # Apply new groups
        for group_entry in submitted_groups:
            try:
                user_id, group_id = group_entry.split(':')
                user = User.objects.get(id=int(user_id))
                group = Group.objects.get(id=int(group_id))
                user.groups.add(group)
            except (ValueError, User.DoesNotExist, Group.DoesNotExist):
                continue
        
        messages.success(request, "Groups and Admin privileges updated successfully!")
        return redirect('manage_permissions')

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        users = User.objects.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        ).distinct()
    else:
        users = User.objects.all()
        
    # Annotate users for template
    for user in users:
        user.user_group_ids = user.groups.values_list('id', flat=True)

    return render(request, 'indent/manage_permissions.html', {
        'users': users,
        'groups': groups,
        'departments': departments,
        'search_query': search_query,
    })
