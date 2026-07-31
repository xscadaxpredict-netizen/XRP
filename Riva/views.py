from .models import DealershipPricing
import json
import shutil
from django.shortcuts import render,redirect
from django.http import JsonResponse,HttpResponse
from Riva.models import ConfirmedOrderFollowUp, FollowUp, Enquiry, ConfirmedHidrecWash
from .models import  Enquiry, Hidrec_wash,Products,Executive,FileUploadModel, quotation, ConfirmedOrder,FollowUp,companydetails
from .forms import ConfirmedOrderForm
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404
from django.core .paginator import Paginator
from django.db.models import Q,ForeignKey
import csv
import xlwt
import openpyxl
from django.template.loader import render_to_string
from xhtml2pdf import pisa

from reportlab.pdfgen import canvas
from io import BytesIO

# Create your views here.
def Home(request):
    current_user = request.user

    # Fetch the follow-ups of the current user or all follow-ups for superusers
    if curent_user.is_staff or current_user.is_superuser:
        # Include follow-ups from all confirmed orders as well
        followups = FollowUp.objects.all().order_by('-fodate', '-fotime')
    else:
        # Include follow-ups related to the user's confirmed orders
        followups = FollowUp.objects.filter(user=current_user).order_by('-fodate', '-fotime')
    
    # Fetch follow-ups related to confirmed orders (if any)
    # confirmed_order_followups = FollowUp.objects.filter(order__isnull=False).order_by('-fodate', '-fotime')

    # Combine both sets of follow-ups (user-specific and confirmed order-specific)
    # all_followups = followups | confirmed_order_followups

    # Pass all relevant data to the template
    # return render(request, 'base.html', {'followups': all_followups})
    return render(request, 'base.html')


from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, ForeignKey, Count
from django.contrib.auth.models import User
from django.shortcuts import render
from .models import Enquiry
from app.models import UserProfile, Zone, Division

@login_required
def enq_home(request):
    current_user = request.user

    # ---------------------------
    # GET PARAMS
    # ---------------------------
    selected_user_id = request.GET.get("user", "")
    funnel_layer = request.GET.get("funnel_layer", "")
    search_query = request.GET.get("search", "")
    sort = request.GET.get("sort", "-created_at")

    # ---------------------------
    # BASE QUERY
    # ---------------------------
    base_filter = Q(is_confirmed=False, is_lost=False) | Q(is_reverted=True)

    has_profile = hasattr(current_user, 'userprofile')
    is_xpredict = has_profile and current_user.userprofile.is_xpredict
    is_manager = current_user.is_staff or current_user.is_superuser or is_xpredict

    if is_manager:
        enquiries = Enquiry.objects.filter(base_filter)
    else:
        enquiries = Enquiry.objects.filter(base_filter).filter(created_by=current_user)

    # ---------------------------
    # USER FILTER
    # ---------------------------
    if selected_user_id and selected_user_id != 'all':
        enquiries = enquiries.filter(created_by_id=selected_user_id)

    # ---------------------------
    # FUNNEL FILTER
    # ---------------------------
    if funnel_layer == 'quotation':
        enquiries = enquiries.filter(quotation__isnull=False).distinct()

    # ---------------------------
    # GLOBAL SEARCH
    # ---------------------------
    if search_query:
        search_q = Q()
        for field in Enquiry._meta.fields:
            if isinstance(field, ForeignKey):
                if field.name == 'created_by':
                     search_q |= Q(**{f"{field.name}__username__icontains": search_query})
                     search_q |= Q(**{f"{field.name}__first_name__icontains": search_query})
                else:
                    search_q |= Q(**{f"{field.name}__name__icontains": search_query})
            else:
                search_q |= Q(**{f"{field.name}__icontains": search_query})
        enquiries = enquiries.filter(search_q)

    # ---------------------------
    # SORTING (SAFE)
    # ---------------------------
    allowed_sorts = [
        "status", "-status",
        "created_at", "-created_at",
        "companyname", "-companyname",
        "id", "-id",
    ]
    if sort not in allowed_sorts:
        sort = "-created_at"

    enquiries = enquiries.order_by(sort)

    # ---------------------------
    # OPTIMIZATION
    # ---------------------------
    enquiries = enquiries.prefetch_related("files", "followups")

    # ---------------------------
    # PAGINATION
    # ---------------------------
    paginator = Paginator(enquiries, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    for enquiry in page_obj:
        enquiry.followups_list = list(
            enquiry.followups.order_by("-fodate", "-fotime")
        )

    # ---------------------------
    # USERS FOR DROPDOWN (FIXED)
    # ---------------------------
    if is_manager:
        users_list = (
            User.objects
            .filter(enquiry__isnull=False)
            .annotate(enquiry_count=Count("enquiry"))
            .distinct()
            .order_by("first_name", "username")
        )
    else:
        users_list = User.objects.filter(id=current_user.id)

    # ---------------------------
    # CONTEXT
    # ---------------------------
    context = {
        "page_obj": page_obj,
        "users_list": users_list,
        "selected_user_id": selected_user_id if selected_user_id == 'all' else (int(selected_user_id) if selected_user_id else ""),
        "search_query": search_query,
        "current_sort": sort,
    }

    return render(request, "xp2/enqhome.html", context)

   

def enquiry_view(request):
    users=User.objects.all()
    products=Products.objects.all()
    executive=Executive.objects.all()
    return render(request, 'xp2/newenquiry.html',{'products':products , 'users':users,'executive':executive,})

from django.http import JsonResponse

@login_required
def check_duplicate_api(request):
    """
    AJAX endpoint for real-time duplicate checking on the new enquiry form.
    Returns JSON { 'exists': bool, 'message': str }
    """
    company_name = request.GET.get('companyname', '').strip()
    email = request.GET.get('email', '').strip()
    
    if not company_name and not email:
        return JsonResponse({'exists': False})
        
    from django.db.models import Q
    dup_query = Q()
    if company_name:
        dup_query |= Q(companyname__iexact=company_name)
    if email:
        dup_query |= Q(email__iexact=email)
        
    duplicate = Enquiry.objects.filter(dup_query).first()
    
    if duplicate:
        # Check permissions for blocking
        current_user = request.user
        has_profile = hasattr(current_user, 'userprofile')
        is_xpredict = has_profile and current_user.userprofile.is_xpredict
        is_internal = current_user.is_superuser or current_user.is_staff or is_xpredict
        
        creator = duplicate.created_by
        dup_is_internal = False
        if creator:
            has_prof = hasattr(creator, 'userprofile')
            dup_is_xpredict = has_prof and creator.userprofile.is_xpredict
            dup_is_internal = creator.is_superuser or creator.is_staff or dup_is_xpredict
            
        blocked = is_internal or dup_is_internal

        # Construct message based on what matched
        match_reason = []
        if company_name and duplicate.companyname and company_name.lower() == duplicate.companyname.lower():
            match_reason.append(f"company name '{duplicate.companyname}'")
        if email and duplicate.email and email.lower() == duplicate.email.lower():
            match_reason.append(f"email '{duplicate.email}'")
            
        reason_str = " and ".join(match_reason) if match_reason else "similar details"
        message = f"An enquiry with this {reason_str} already exists (ID: {duplicate.id})."
        
        return JsonResponse({'exists': True, 'message': message, 'blocked': blocked})
        
    return JsonResponse({'exists': False})

def add_data(request):
    if request.method == "POST":
        from django.contrib import messages
        from django.contrib.auth.models import User

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
        remarks = request.POST.get("remarks") or ""
        files = request.FILES.getlist("attachment[]")

        # Duplicate checking logic
        from django.db.models import Q
        current_user = request.user
        has_profile = hasattr(current_user, 'userprofile')
        is_xpredict = has_profile and current_user.userprofile.is_xpredict
        is_internal = current_user.is_superuser or current_user.is_staff or is_xpredict
        
        dup_query = Q(companyname__iexact=company_name)
        if email:
            dup_query |= Q(email__iexact=email)
            
        duplicate_enquiry = Enquiry.objects.filter(dup_query).first()
        
        if duplicate_enquiry:
            creator = duplicate_enquiry.created_by
            dup_is_internal = False
            if creator:
                has_prof = hasattr(creator, 'userprofile')
                dup_is_xpredict = has_prof and creator.userprofile.is_xpredict
                dup_is_internal = creator.is_superuser or creator.is_staff or dup_is_xpredict

            if is_internal or dup_is_internal:
                messages.error(request, f"This enquiry already exists in the system (Company: {duplicate_enquiry.companyname}). Duplication is not permitted.")
                users_list = User.objects.all()
                products_list = Products.objects.all()
                executive_list = Executive.objects.all()
                return render(request, 'xp2/newenquiry.html', {
                    'products': products_list,
                    'users': users_list,
                    'executive': executive_list,
                    'form_data': request.POST,
                })
            else:
                remarks = remarks + f"\n\n[SYSTEM FLAG: POTENTIAL DUPLICATE OF ENQ ID {duplicate_enquiry.id}]"

        try:
            # Validate and fetch related objects
            try:
                executive = Executive.objects.get(id=executive_id) if executive_id else None
            except Executive.DoesNotExist:
                messages.error(request, "Invalid Executive selected.")
                raise ValueError("Invalid Executive")

            try:
                product = Products.objects.get(id=product_id) if product_id else None
            except Products.DoesNotExist:
                messages.error(request, "Invalid Product selected.")
                raise ValueError("Invalid Product")

            # Create and save the enquiry record
            enquiry = Enquiry.objects.create(
                companyname=company_name or "",
                customername=customer_name or "",
                refrence=reference_name or "",
                email=email or None,
                contact=contact or None,
                location=location or "",
                status=status or "",
                products=product,
                subproduct=subproduct or "",
                closuredate=closure_date or None,
                executive=executive,
                remarks=remarks or "",
                created_by=request.user,
            )

            for file in files:
                file_upload = FileUploadModel.objects.create(file=file, name=file.name)
                enquiry.files.add(file_upload)

            enquiry.save()

            # Add visibility for both the logged-in user and selected executive
            enquiry.created_by = request.user  # Ensure the logged-in user is saved as creator
            enquiry.executive = executive  # Ensure the selected executive is assigned
            enquiry.save()

            messages.success(request, "Enquiry added successfully!")
            return redirect("enquries")  # Redirect to enqhome page

        except Exception as e:
            if not messages.get_messages(request):
                messages.error(request, f"An error occurred while saving the enquiry: {str(e)}")
            
            # Reload the newenquiry page with the lists and the POST data
            users_list = User.objects.all()
            products_list = Products.objects.all()
            executive_list = Executive.objects.all()
            return render(request, 'xp2/newenquiry.html', {
                'products': products_list,
                'users': users_list,
                'executive': executive_list,
                'form_data': request.POST,
            })

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

        current_user = request.user
        has_profile = hasattr(current_user, 'userprofile')
        is_xpredict = has_profile and current_user.userprofile.is_xpredict

        return render(request, 'xp2/enquiry_details.html', {
            'enquiry_data': data, 
            'followups': followups, 
            'revert_remarks': revert_remarks,
            'is_xpredict': is_xpredict
        })

    except Enquiry.DoesNotExist:
        return HttpResponse("Enquiry not found", status=404)

    

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Enquiry, FileUploadModel
from .forms import EnquiryForm


@login_required
def edit_enquiry(request, enquiry_id):
    enquiry = get_object_or_404(Enquiry, id=enquiry_id)

    if request.method == "POST":
        form = EnquiryForm(request.POST, instance=enquiry)

        if form.is_valid():
            enquiry = form.save(commit=False)
            enquiry.save()

            # 🔴 REMOVE FILES (only checked ones)
            remove_file_ids = request.POST.getlist("remove_files")
            if remove_file_ids:
                enquiry.files.remove(*remove_file_ids)

            # 🟢 ADD NEW FILES (keep old ones)
            for uploaded_file in request.FILES.getlist("attachment[]"):
                file_obj = FileUploadModel.objects.create(
                    file=uploaded_file,
                    name=uploaded_file.name
                )
                enquiry.files.add(file_obj)

            messages.success(request, "Enquiry updated successfully.")
            return redirect("enquiry_details", id=enquiry.id)

    else:
        form = EnquiryForm(instance=enquiry)

    return render(request, "xp2/edit_enquiry.html", {
        "form": form,
        "enquiry": enquiry
    })



from django.shortcuts import render
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Enquiry

from django.db.models import Q

def lost_orders_view(request):
    current_user = request.user
    selected_user_id = request.GET.get('user')
    selected_user = None

    # Admin users can view all users and filter by selected user
    users = User.objects.all()
    if selected_user_id and selected_user_id != 'all':
        selected_user = User.objects.filter(id=selected_user_id).first()

    # Search functionality
    search_query = request.GET.get('search', '')
    global_filter = Q()

    # Define the fields you want to search
    searchable_fields = [
        'companyname',
        'customername',
        'id',
        'contact',
        'remarks',
        'email',
        'location',
        'status',
        'executive__name',  # If executive is a foreign key and you want to search the name
    ]

    # Loop through each field and apply the search filter
    if search_query:
        for field in searchable_fields:
            global_filter |= Q(**{f"{field}__icontains": search_query})

    # Determine the queryset based on user type
    if current_user.is_staff or current_user.is_superuser:
        # Superusers can view all lost enquiries and relegated confirmed_enquiry records
        lost_enquiries = Enquiry.objects.filter(is_lost=True).filter(global_filter)
        relegated_enquiries = Enquiry.objects.filter(is_relegated=True).filter(global_filter)
    else:
        # Non-superusers can only view their own lost or relegated enquiries
        lost_enquiries = Enquiry.objects.filter(is_lost=True, created_by=current_user).filter(global_filter)
        relegated_enquiries = Enquiry.objects.filter(
            is_relegated=True,
            created_by=current_user
        ).filter(global_filter)

    # Combine the two querysets using `union`
    combined_enquiries = lost_enquiries
    relegated=confirmed_enquiry.objects.filter(relegate=True)
    print(f"rel",relegated)
    print(f"comb",combined_enquiries)
    # Return the response with the filtered lost and relegated enquiries
    return render(request, 'xp2/lost_orders.html', {
        'lost_enquiries': combined_enquiries,
        'relegated':relegated,
        'search_query': search_query,
        'users': users,
        'selected_user': selected_user,
    })

 
   


from django.shortcuts import get_object_or_404, redirect
from .models import Enquiry
from django.contrib import messages 

def push_to_lost_order(request, id):
    reason = request.POST.get('reason', '').strip()
    enquiry = get_object_or_404(Enquiry, id=id)
    enquiry.is_lost = True  # Mark as lost
    enquiry.is_reverted = False
    enquiry.flag = reason  # Save the reason
    enquiry.save()

    messages.success(request, "Enquiry successfully moved to Lost Orders.")
    return redirect('lost_orders')  # Redirect to the Lost Orders page
  
def delete_lost_order(request, id):
    enquiry = get_object_or_404(Enquiry, id=id)
    enquiry.delete()

    messages.success(request, "Lost order deleted successfully.")
    return redirect('lost_orders')


def retrieve_lost_order(request, id):
    # Fetch the Enquiry object or return 404 if not found
    enquiry = get_object_or_404(Enquiry, id=id)

    # Check if the enquiry is relegated
    if enquiry.is_relegated:
        enquiry.is_reverted = True  # Mark as reverted
        enquiry.is_relegated = False  # Unmark as relegated

    # Always unmark as lost
    enquiry.is_lost = False  # Mark as active
    enquiry.save()  # Save the changes

    # Display success message
    messages.success(request, "Enquiry successfully retrieved from Lost Orders.")
    return redirect('enquries')  # Redirect to the enquiries page


from collections import defaultdict

import json
import os
from collections import defaultdict
from django.conf import settings
from django.shortcuts import render, get_object_or_404
from .models import Enquiry, CommercialQuote
import os
import json
from collections import defaultdict
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from .models import Enquiry, CommercialQuote

def manage_quotation(request, enquiry_id):
    enquiry = get_object_or_404(Enquiry, id=enquiry_id)

    # Get quotations filtered by enquiry_id
    quotations = CommercialQuote.objects.filter(enquiry_id=enquiry_id).order_by('-id')
    hidrec=ConfirmedHidrecWash.objects.filter(enquiry_id=enquiry_id).order_by('-id')
    # Initialize file paths for 'stored_data' and 'proposal'
    base_dir = settings.BASE_DIR
    stored_data_path = os.path.join(base_dir, 'stored_data')
    proposal_path = os.path.join(base_dir, 'proposal')
    draft_path=os.path.join(base_dir, 'AMC_draft')
    proposal_draft_path=os.path.join(base_dir, 'proposal_draft')

    # Lists to hold file paths for 'stored_data' and 'proposal'
    all_stored_files = []
    all_proposal_files = []
    all_draft_files=[]
    all_proposal_draft_files=[]

    # Data containers for each category
    stored_data = defaultdict(list)
    proposal_data = defaultdict(list)
    draft_data=defaultdict(list)
    proposal_draft_data=defaultdict(list)

    # Process files in 'stored_data'
    stored_data_directories = os.listdir(stored_data_path)
    for directory in stored_data_directories:
        dir_path = os.path.join(stored_data_path, directory)
        if os.path.isdir(dir_path) and directory == str(enquiry_id):
            json_files = os.listdir(dir_path)
            for json_file in json_files:
                file_path = os.path.join(dir_path, json_file)
                all_stored_files.append(file_path)
    # draft files            
    stored_data_directories = os.listdir(draft_path)
    for directory in stored_data_directories:
        dir_path = os.path.join(draft_path, directory)
        if os.path.isdir(dir_path) and directory == str(enquiry_id):
            json_files = os.listdir(dir_path)
            for json_file in json_files:
                file_path = os.path.join(dir_path, json_file)
                all_draft_files.append(file_path)

    # Process files in 'proposal'
    proposal_directories = os.listdir(proposal_path)
    for directory in proposal_directories:
        dir_path = os.path.join(proposal_path, directory)
        if os.path.isdir(dir_path) and directory == str(enquiry_id):
            json_files = os.listdir(dir_path)
            for json_file in json_files:
                file_path = os.path.join(dir_path, json_file)
                all_proposal_files.append(file_path)

    # Process files in 'proposal_draft'
    proposal_directories = os.listdir(proposal_draft_path)
    for directory in proposal_directories:
        dir_path = os.path.join(proposal_draft_path, directory)
        if os.path.isdir(dir_path) and directory == str(enquiry_id):
            json_files = os.listdir(dir_path)
            for json_file in json_files:
                file_path = os.path.join(dir_path, json_file)
                all_proposal_draft_files.append(file_path)

    # Load data from files in 'stored_data'
    for file_path in all_stored_files:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                try:
                    data = json.load(file)
                    if isinstance(data, dict) and 'enquiry_id' in data:
                        if str(data['enquiry_id']) == str(enquiry_id):
                            stored_data[os.path.basename(file_path)].append(data)
                        else:
                            stored_data[os.path.basename(file_path)].append({'error': f'Mismatch enquiry_id: {data["enquiry_id"]}'})
                    else:
                        stored_data[os.path.basename(file_path)].append({'error': 'Missing enquiry_id in JSON'})
                except json.JSONDecodeError:
                    stored_data[os.path.basename(file_path)].append({'error': 'Invalid JSON file'})
        else:
            stored_data[os.path.basename(file_path)].append({'error': 'File not found'})
    #draft
    for file_path in all_draft_files:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                try:
                    data = json.load(file)
                    if isinstance(data, dict) and 'enquiry_id' in data:
                        if str(data['enquiry_id']) == str(enquiry_id):
                            draft_data[os.path.basename(file_path)].append(data)
                        else:
                            draft_data[os.path.basename(file_path)].append({'error': f'Mismatch enquiry_id: {data["enquiry_id"]}'})
                    else:
                        draft_data[os.path.basename(file_path)].append({'error': 'Missing enquiry_id in JSON'})
                except json.JSONDecodeError:
                    draft_data[os.path.basename(file_path)].append({'error': 'Invalid JSON file'})
        else:
            draft_data[os.path.basename(file_path)].append({'error': 'File not found'})

    # Load data from files in 'proposal'
    for file_path in all_proposal_files:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                try:
                    data = json.load(file)
                    if isinstance(data, dict) and 'enquiry_id' in data:
                        if str(data['enquiry_id']) == str(enquiry_id):
                            proposal_data[os.path.basename(file_path)].append(data)
                        else:
                            proposal_data[os.path.basename(file_path)].append({'error': f'Mismatch enquiry_id: {data["enquiry_id"]}'})
                    else:
                        proposal_data[os.path.basename(file_path)].append({'error': 'Missing enquiry_id in JSON'})
                except json.JSONDecodeError:
                    proposal_data[os.path.basename(file_path)].append({'error': 'Invalid JSON file'})
        else:
            proposal_data[os.path.basename(file_path)].append({'error': 'File not found'})

    # Load data from files in 'proposal_draft'
    for file_path in all_proposal_draft_files:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                try:
                    data = json.load(file)
                    if isinstance(data, dict) and 'enquiry_id' in data:
                        if str(data['enquiry_id']) == str(enquiry_id):
                            proposal_draft_data[os.path.basename(file_path)].append(data)
                        else:
                            proposal_draft_data[os.path.basename(file_path)].append({'error': f'Mismatch enquiry_id: {data["enquiry_id"]}'})
                    else:
                        proposal_draft_data[os.path.basename(file_path)].append({'error': 'Missing enquiry_id in JSON'})
                except json.JSONDecodeError:
                    proposal_draft_data[os.path.basename(file_path)].append({'error': 'Invalid JSON file'})
        else:
            proposal_draft_data[os.path.basename(file_path)].append({'error': 'File not found'})
   
    # Pass the data to the template
    has_profile = hasattr(request.user, 'userprofile')
    is_xpredict = has_profile and request.user.userprofile.is_xpredict

    return render(request, 'xp2/manage_quotation.html', {
        'enquiry': enquiry,
        'hidrec':hidrec,
        'quotations': quotations,
        'stored_data': dict(stored_data),  # Convert defaultdict to a standard dict for the template
        'proposal_data': dict(proposal_data),
        'draft_data':dict(draft_data),
        'proposal_draft_data':dict(proposal_draft_data),
        'uploaded_quotations': UploadedQuote.objects.filter(enquiry_id=enquiry_id),
        'is_xpredict': is_xpredict,
    })


























# def manage_quotation(request, enquiry_id):
#     enquiry = get_object_or_404(Enquiry, id=enquiry_id)
    
#     quotations = CommercialQuote.objects.filter(enquiry_id=enquiry_id).order_by('-id')
    
#     base_dir = settings.BASE_DIR
#     file_path = os.path.join(base_dir, 'stored_data')
#     a = os.listdir(file_path)
#     file_j = []
#     full_j = []
#     for file in a:
#         file_j.append(os.path.join(base_dir,'stored_data',file))

#     for file_j1 in file_j:
#         b = os.listdir(file_j1)
#         for i in b:
#             full_j.append(os.path.join(file_j1,i))
    
#     print(full_j)
#     for p in full_j:
#         if os.path.exists(p):
#             print(p)
#             with open(p, 'r') as file:
#                 data = json.load(file)  # Now 'data' should be a list or dict with multiple items
#                 print(data)
#         else:
#             data = {'error': 'File not found'}
#             print(data)
#             print(f"File path: {p}")
    
#     return render(request, 'xp2/manage_quotation.html', {
#         'enquiry': enquiry,
#         'quotations': quotations,
#         'enquiry_id': enquiry_id,
#         'data': data,  
#     })


import os
def quotation_details(request, quotation_id):
    # Retrieve the quotation object and the related enquiry object
    quotations = get_object_or_404(quotation, id=quotation_id)
    enquiry = quotations.qid  # Accessing the Enquiry related to the Quotation
    
    # Fetch the related files of the enquiry
    files = enquiry.files.all()  # Assuming `files` is the related_name in Enquiry model

    # Extract the filename for BOQ and Quote (strip directory path)
    boq_file_name = os.path.basename(quotations.boq.name) if quotations.boq else None
    quote_file_name = os.path.basename(quotations.quote.name) if quotations.quote else None

    # Render the template with quotation, enquiry, and files
    return render(request, 'xp2/quotation_details.html', {
        'quotations': quotations,
        'enquiry': enquiry,
        'files': files,  # Pass the files to the template
        'boq_file_name': boq_file_name,
        'quote_file_name': quote_file_name,
    })



import os
import json
from collections import defaultdict
from django.shortcuts import render, get_object_or_404, redirect
from django.conf import settings
from .models import (
    Enquiry, CommercialQuote, confirmed_enquiry, ConfirmedHidrecWash, UploadedQuote
)

def confirm_order(request, enquiry_id):
    enquiry = get_object_or_404(Enquiry, id=enquiry_id)
    
    # Fetch commercial quotations for this enquiry
    quotations = CommercialQuote.objects.filter(enquiry_id=enquiry_id).order_by('-id')
    
    # Fetch confirmed quotations to disable already confirmed ones
    confirmed_qs = confirmed_enquiry.objects.filter(enquiry=enquiry)
    confirmed_quotations = set(confirmed_qs.values_list('quotation', flat=True))
    
    # Paths for stored data and proposals
    base_dir = settings.BASE_DIR
    stored_data_path = os.path.join(base_dir, 'stored_data')
    proposal_path = os.path.join(base_dir, 'proposal')
    
    stored_data = defaultdict(list)
    proposal_data = defaultdict(list)
    
    # Load JSON data from stored_data directory for this enquiry
    if os.path.exists(stored_data_path):
        for directory in os.listdir(stored_data_path):
            dir_path = os.path.join(stored_data_path, directory)
            if os.path.isdir(dir_path) and directory == str(enquiry_id):
                for json_file in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, json_file)
                    if os.path.exists(file_path):
                        with open(file_path, 'r') as f:
                            try:
                                data = json.load(f)
                                if isinstance(data, dict) and str(data.get('enquiry_id')) == str(enquiry_id):
                                    stored_data[os.path.basename(file_path)].append(data)
                            except json.JSONDecodeError:
                                stored_data[os.path.basename(file_path)].append({'error': 'Invalid JSON file'})
    
    # Load JSON data from proposal directory for this enquiry
    if os.path.exists(proposal_path):
        for directory in os.listdir(proposal_path):
            dir_path = os.path.join(proposal_path, directory)
            if os.path.isdir(dir_path) and directory == str(enquiry_id):
                for json_file in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, json_file)
                    if os.path.exists(file_path):
                        with open(file_path, 'r') as f:
                            try:
                                data = json.load(f)
                                if isinstance(data, dict) and str(data.get('enquiry_id')) == str(enquiry_id):
                                    proposal_data[os.path.basename(file_path)].append(data)
                            except json.JSONDecodeError:
                                proposal_data[os.path.basename(file_path)].append({'error': 'Invalid JSON file'})
    
    # Fetch Hydric Wash quotations for this enquiry 
    hidrec_quotations = ConfirmedHidrecWash.objects.filter(enquiry_id=enquiry_id)
    
    # Fetch Uploaded quotes for this enquiry
    uploaded_quotations = UploadedQuote.objects.filter(enquiry_id=enquiry_id)
    
    if request.method == 'POST':
        selected_quotation_nos = request.POST.getlist('quotation_selection')
        po_files = request.FILES.getlist('po_file')
        print('POST:', request.POST)
        print('FILES:', request.FILES)

        if not selected_quotation_nos:
            return render(request, 'xp2/confirm_order.html', {
                'enquiry': enquiry,
                'quotations': quotations,
                'stored_data': dict(stored_data),
                'proposal_data': dict(proposal_data),
                'confirmed_quotations': confirmed_quotations,
                'hidrec_quotations': hidrec_quotations,
                'uploaded_quotations': uploaded_quotations,
                'error': 'Please select at least one quotation.',
            })

        # Save the confirmed quotations
        for selected_quotation_no in selected_quotation_nos:
            confirmed_entry = confirmed_enquiry.objects.create(
                created_by=request.user,
                enquiry=enquiry,
                quotation=selected_quotation_no,
            )

        # Save PO files if uploaded
        if po_files:
            import time
            for i, po_file in enumerate(po_files):
                # Need a unique quotation number, generic to the enquiry
                unique_po_no = f"PO_ENQ{enquiry.id}_{int(time.time())}_{i}"
                UploadedQuote.objects.create(
                    enquiry=enquiry,
                    quote_type='Purchase Order (PO)',
                    file=po_file,
                    quotation_no=unique_po_no
                )

        # Mark the enquiry as confirmed (reset reverted flag optionally)
        if not enquiry.oc_number:
            enquiry.oc_number = f"OC-ENQ{enquiry.id}"
        enquiry.is_confirmed = True
        enquiry.is_reverted = False
        enquiry.save()

        return redirect('confirmed_orders')

    context = {
        'enquiry': enquiry,
        'quotations': quotations,
        'stored_data': dict(stored_data),
        'proposal_data': dict(proposal_data),
        'confirmed_quotations': confirmed_quotations,
        'hidrec_quotations': hidrec_quotations,
        'uploaded_quotations': uploaded_quotations,
    }
    return render(request, 'xp2/confirm_order.html', context)




from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import render, redirect
from .models import Enquiry

def confirmed_orders(request):
    current_user = request.user
    selected_user_id = request.GET.get('user')
    selected_user = None

    if selected_user_id and selected_user_id != 'all':
        selected_user = User.objects.filter(id=selected_user_id).first()

    # Base queryset for confirmed enquiries
    confirmed_filter = Q(is_confirmed=True)

    if current_user.is_staff or current_user.is_superuser:
        # Admin/staff can view all confirmed orders
        confirmed_orders = Enquiry.objects.filter(confirmed_filter).prefetch_related('confirmed_enquiry_set')
    else:
        # Regular users can view only their own confirmed orders
        confirmed_orders = Enquiry.objects.filter(
            confirmed_filter,
            Q(created_by=current_user) | Q(executive__name=current_user.username)  # if executive is ForeignKey
            # Q(created_by=current_user) | Q(executive=current_user.username)  # if executive is CharField
        ).prefetch_related('confirmed_enquiry_set')

    # Global search
    search_query = request.GET.get('search', '')
    if search_query:
        global_filter = Q()
        searchable_fields = [
            'companyname',
            'customername',
            'id',
            'contact',
            'closuredate',
            'executive__name',  # if ForeignKey
            # 'executive',       # if CharField
        ]
        for field in searchable_fields:
            global_filter |= Q(**{f"{field}__icontains": search_query})
        confirmed_orders = confirmed_orders.filter(global_filter)

    confirmed_orders = confirmed_orders.distinct()

    # Handle reverting confirmed status
    if 'revert' in request.GET:
        enquiry_id = request.GET.get('revert')
        enquiry = Enquiry.objects.filter(id=enquiry_id).first()
        if enquiry:
            if enquiry.is_confirmed:
                enquiry.is_reverted = False
            else:
                enquiry.is_reverted = not enquiry.is_reverted
            enquiry.save()
        return redirect('confirmed_orders')

    # Handle pushing new quotation number
    if 'push' in request.GET:
        enquiry_id = request.GET.get('push')
        new_quotation_number = request.GET.get('quotation_number')
        enquiry = Enquiry.objects.filter(id=enquiry_id).first()
        if enquiry:
            if enquiry.quotation != new_quotation_number:
                enquiry.quotation = new_quotation_number
                enquiry.is_reverted = False
                enquiry.save()
        return redirect('confirmed_orders')

    return render(request, 'xp2/confirmed_orders.html', {
        'confirmed_orders': confirmed_orders,
        'search_query': search_query,
        'selected_user': selected_user,
    })


def add_followup(request, enquiry_id):
    followups = FollowUp.objects.all()
    if request.method == "POST":
        enquiry = get_object_or_404(Enquiry, id=enquiry_id)
        foname = request.POST.get('foname')
        fodate_str = request.POST.get('fodate')
        fotime_str = request.POST.get('fotime')
        
        # Ensure fodate is a valid datetime object
        try:
            fodate = datetime.strptime(fodate_str, '%Y-%m-%d')  # Adjust the format as per your needs
        except ValueError:

            return redirect('enquiry_details', id=enquiry_id)

        # Ensure fotime is a valid time object
        try:
            fotime = datetime.strptime(fotime_str, '%H:%M').time()  # Adjust the format as per your needs
        except ValueError:

            return redirect('enquiry_details', id=enquiry_id)

        if foname and fodate and fotime:
            FollowUp.objects.create(
                enquiry=enquiry,
                foname=foname,
                fodate=fodate,
                fotime=fotime,

                
            )


            return redirect('enquiry_details', id=enquiry_id)


        return redirect('enquiry_details', id=enquiry_id)
    
    return HttpResponse("Invalid request", status=400)


def push_to_lost_order_from_confirmed(request, enquiry_id, quotation_no):
    # Fetch the confirmed_enquiry record based on the quotation number
    confirmed_order = confirmed_enquiry.objects.filter(quotation=quotation_no).first()

    if not confirmed_order:
        messages.error(request, "No confirmed order found with the given quotation number.")
        return redirect('confirmed_orders')  # Redirect back if no confirmed order found

    # Access the related Enquiry object via the ForeignKey
    enquiry = confirmed_order.enquiry  # Access the related Enquiry object

    # Get the reason for moving the order to Lost Orders
    reason = request.POST.get("reason", "").strip()

    if not reason:
        messages.error(request, "Please provide a reason for moving the order to Lost Orders.")
        return redirect('confirmed_orders')  # Redirect back if no reason is provided

    # Update the 'relegate' field for the specific confirmed_enquiry
    confirmed_order.relegate = True
    confirmed_order.save()  # Save the updated confirmed_enquiry record

    # Also update the 'is_relegated' field of the related Enquiry object
    if enquiry:
        enquiry.is_relegated = True
        enquiry.save()  # Save the updated Enquiry record

    # Add success message
    messages.success(request, f"Quotation {quotation_no} successfully moved to Lost Orders and Enquiry relegated.")

    # Redirect to Lost Orders page
    return redirect('lost_orders')

 
def confirmed_view(request, enquiry_id, quotation_no):
    try:
        # Fetch all confirmed enquiries for the given enquiry_id
        confirmed_quotations = confirmed_enquiry.objects.filter(enquiry_id=enquiry_id)

        # Determine the quotation type based on the prefix
        if quotation_no.startswith("EL-HID-CM"):
            quotation_type = "commercial"
        elif quotation_no.startswith("EL-HID-AMCPR"):
            quotation_type = "amc"
        elif quotation_no.startswith("EL-HID-PR"):
            quotation_type = "proposal"
        else:
            quotation_type = "unknown"

        if not confirmed_quotations.exists():
            return render(request, 'xp2/confirmed_view.html', {
                'error': f"No confirmed enquiry found for enquiry ID {enquiry_id}",
            })

        order = confirmed_quotations.filter(quotation=quotation_no).first()
        if not order:
            return render(request, 'xp2/confirmed_view.html', {
                'error': f"No confirmed enquiry found with quotation number {quotation_no} for enquiry ID {enquiry_id}",
            })

        followups = ConfirmedOrderFollowUp.objects.filter(confirmed_order=order)

    except confirmed_enquiry.DoesNotExist:
        return render(request, 'xp2/confirmed_view.html', {
            'error': f"No confirmed enquiry found for enquiry ID {enquiry_id}",
        })

    enquiry = order.enquiry

    # Pass enquiry object (with valid ID) to the template
    return render(request, 'xp2/confirmed_view.html', {
        'order': order,
        'enquiry': enquiry,                  # Pass the 'enquiry' object here
        'quotations': confirmed_quotations,  # All confirmed enquiries
        'followups': followups,
        'enquiry_id': enquiry_id,            # Ensure this is set correctly
        'quotation_number': quotation_no,
        'quotation_type': quotation_type,
    })


from django.shortcuts import render, get_object_or_404, redirect
from Riva.models import ConfirmedOrderFollowUp, confirmed_enquiry

def add_confirmed_order_followup(request, enquiry_id, quotation_no):
    # Fetch the confirmed order based on enquiry_id and quotation_no
    try:
        order = confirmed_enquiry.objects.get(enquiry_id=enquiry_id, quotation=quotation_no)
    except confirmed_enquiry.DoesNotExist:
        return render(request, 'xp2/confirmed_view.html', {
            'error': f"No confirmed order found for enquiry ID {enquiry_id} and quotation {quotation_no}",
        })
    except confirmed_enquiry.MultipleObjectsReturned:
        return render(request, 'xp2/confirmed_view.html', {
            'error': f"Multiple confirmed orders found for enquiry ID {enquiry_id} and quotation {quotation_no}",
        })

    if request.method == 'POST':
        # Get the form data from the request
        foname = request.POST.get('foname')
        fodate = request.POST.get('fodate')
        fotime = request.POST.get('fotime')

        # Create a new follow-up associated with the confirmed order
        ConfirmedOrderFollowUp.objects.create(
            confirmed_order=order,
            foname=foname,
            fodate=fodate,
            fotime=fotime
        )

        # Redirect to the same page to display updated follow-ups
        return redirect('confirmed_view',quotation_no=quotation_no , enquiry_id=enquiry_id)

    # Get all follow-ups for the current confirmed order
    followups = ConfirmedOrderFollowUp.objects.filter(confirmed_order=order)

    # Render the template with the confirmed order and its follow-ups
    return render(request, 'xp2/confirmed_view.html', {
        'order': order,
        'followups': followups,
        'enquiry_id': enquiry_id,         
        'quotation_number': quotation_no,
    })


from django.db.models.functions import TruncMonth
from django.db.models import Count, Sum
from django.shortcuts import render
from .models import Enquiry, ConfirmedOrder
from app.models import Target ,UserProfile,User


def dashboard(request):
    followups = FollowUp.objects.all().order_by('-fodate', '-fotime')
    
    current_user = request.user
    has_profile = hasattr(current_user, 'userprofile')
    is_xpredict = has_profile and current_user.userprofile.is_xpredict
    is_manager = current_user.is_staff or current_user.is_superuser or is_xpredict
    
    # Get the selected user from the dropdown, default to logged-in user if no selection is made
    default_user = 'all' if is_manager else str(request.user.id)
    selected_user_id = request.POST.get('user') if request.method == 'POST' else request.GET.get('user', default_user)
    
    if selected_user_id == 'all':
        selected_user = None
        base_enquiries = Enquiry.objects.all()
        base_confirmed = ConfirmedOrder.objects.all()
        base_quotes = quotation.objects.all()
        userprofile = None
        target = None
        total_target = None
    else:
        try:
            selected_user = User.objects.get(id=selected_user_id)
            selected_user_id = str(selected_user.id)
        except (User.DoesNotExist, ValueError):
            selected_user = request.user
            selected_user_id = str(selected_user.id)
            
        userprofile = UserProfile.objects.filter(user=selected_user).first()
        target = userprofile.target if userprofile else None
        total_target = Target.objects.filter(userprofile=userprofile).first()
        
        base_enquiries = Enquiry.objects.filter(created_by=selected_user)
        base_confirmed = ConfirmedOrder.objects.filter(created_by=selected_user)
        base_quotes = quotation.objects.filter(created_by=selected_user)
    
    if not request.user.is_authenticated:
        return redirect('login')

    total_enquiries = base_enquiries.count()
    lost_enquiries = base_enquiries.filter(status='lost').count()
    active_enquiries = base_enquiries.filter(status='active').count()
    confirmed_orders = base_confirmed.count()
    lost_orders = base_enquiries.filter(is_lost=True).count()
    total_quotes = base_quotes.count()

    total_revenue = base_quotes.aggregate(total_revenue=Sum('finalamount'))['total_revenue'] or 0
    if isinstance(total_revenue, str):
        total_revenue = float(total_revenue) if total_revenue else 0

    if total_enquiries > 0:
        conversion_ratio = (confirmed_orders / total_enquiries) * 100
    else:
        conversion_ratio = 0

    target_value = 0
    if total_target and total_target.value:
        try:
            target_value = float(total_target.value)
            if target_value > 0:
                target_ratio = (confirmed_orders / target_value) * 100
            else:
                target_ratio = 0
        except ValueError:
            target_ratio = 0
    else:
        target_ratio = 0

    target_to_reach = max(0, int(target_value - confirmed_orders))

    monthly_data = (
        base_enquiries
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    labels = [data['month'].strftime('%B') for data in monthly_data]
    data = [data['count'] for data in monthly_data]

    # Funnel Metrics
    funnel_enquiry_count = base_enquiries.filter(is_lost=False, is_confirmed=False).count()
    funnel_quotation_count = base_enquiries.filter(quotation__isnull=False, is_lost=False, is_confirmed=False).distinct().count()
    funnel_confirmed_count = confirmed_orders
    funnel_lost_count = lost_orders

    users = User.objects.all()

    context = {
        'total_enquiries': total_enquiries,
        'lost_enquiries': lost_enquiries,
        'active_enquiries': active_enquiries,
        'confirmed_orders': confirmed_orders,
        'lost_orders': lost_orders,
        'conversion_ratio': conversion_ratio,
        'monthly_labels': labels,
        'monthly_data': data,
        'total_quotes': total_quotes,
        'total_revenue': total_revenue,
        'target': target,
        'target_ratio': target_ratio,
        'target_to_reach': target_to_reach,
        'users': users,
        'selected_user': selected_user,
        'selected_user_id': selected_user_id,
        'followups': followups,
        'funnel_enquiry_count': funnel_enquiry_count,
        'funnel_quotation_count': funnel_quotation_count,
        'funnel_confirmed_count': funnel_confirmed_count,
        'funnel_lost_count': funnel_lost_count,
    }

    return render(request, 'xp2/dashboard.html', context)


from django.utils import timezone

from datetime import date

def dealership_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')

    current_user = request.user
    has_profile = hasattr(current_user, 'userprofile')
    is_xpredict = has_profile and current_user.userprofile.is_xpredict

    # Check if they are Xpredict admin or staff
    is_manager = current_user.is_staff or current_user.is_superuser or is_xpredict
    view_mode = request.GET.get('view', 'yearly')
    if view_mode not in ['yearly', 'quarterly', 'monthly']:
        view_mode = 'yearly'

    dealerships_data = []
    
    # Resolve target dealerships
    if is_manager:
        all_dealerships = Dealership.objects.all()
    else:
        all_dealerships = current_user.dealerships.all()

    today = timezone.now().date()
    
    # Calculate period date range
    if view_mode == 'monthly':
        period_start = today.replace(day=1)
        if period_start.month == 12:
            period_end = period_start.replace(year=period_start.year + 1, month=1, day=1) - timezone.timedelta(days=1)
        else:
            period_end = period_start.replace(month=period_start.month + 1, day=1) - timezone.timedelta(days=1)
    elif view_mode == 'quarterly':
        current_quarter = (today.month - 1) // 3 + 1
        period_start = today.replace(month=(current_quarter - 1) * 3 + 1, day=1)
        if current_quarter == 4:
            period_end = today.replace(year=today.year + 1, month=1, day=1) - timezone.timedelta(days=1)
        else:
            period_end = today.replace(month=current_quarter * 3 + 1, day=1) - timezone.timedelta(days=1)
    else:
        period_start = today.replace(month=1, day=1)
        period_end = today.replace(month=12, day=31)

    for ds in all_dealerships:
        members = ds.members.all()
        
        # Contract ranges
        start_date = ds.start_date or today.replace(month=1, day=1)
        end_date = ds.end_date or today.replace(month=12, day=31)
        
        total_days = max(1, (end_date - start_date).days)
        days_elapsed = max(0, min((today - start_date).days, total_days))
        days_remaining = max(1, total_days - days_elapsed)
        
        expected_ratio = days_elapsed / total_days if total_days > 0 else 1.0
        expected_orders_ytd = ds.target_orders * expected_ratio
        expected_revenue_ytd = float(ds.target_revenue) * expected_ratio
        
        # YTD actuals
        actual_orders_ytd = ConfirmedOrder.objects.filter(created_by__in=members, project_closing_date__range=(start_date, today)).count()
        actual_revenue_ytd_val = ConfirmedOrder.objects.filter(created_by__in=members, project_closing_date__range=(start_date, today)).aggregate(total_rev=Sum('quotation__finalamount'))['total_rev'] or 0
        actual_revenue_ytd = float(actual_revenue_ytd_val)
        
        # Remaining targets
        remaining_orders_needed = max(0, ds.target_orders - actual_orders_ytd)
        remaining_revenue_needed = max(0.0, float(ds.target_revenue) - actual_revenue_ytd)
        
        # Period-specific calculations
        if view_mode == 'monthly':
            std_target_orders = ds.target_orders / 12.0
            std_target_revenue = float(ds.target_revenue) / 12.0
            
            # Adjusted target: orders needed divided by remaining time, scaled to 1 month
            adjusted_target_orders = (remaining_orders_needed / days_remaining) * 30.4 if days_remaining > 0 else std_target_orders
            adjusted_target_revenue = (remaining_revenue_needed / days_remaining) * 30.4 if days_remaining > 0 else std_target_revenue
            
            # Actuals in current calendar month
            actual_orders_period = ConfirmedOrder.objects.filter(created_by__in=members, project_closing_date__range=(period_start, period_end)).count()
            actual_revenue_period_val = ConfirmedOrder.objects.filter(created_by__in=members, project_closing_date__range=(period_start, period_end)).aggregate(total_rev=Sum('quotation__finalamount'))['total_rev'] or 0
            actual_revenue_period = float(actual_revenue_period_val)
            
        elif view_mode == 'quarterly':
            std_target_orders = ds.target_orders / 4.0
            std_target_revenue = float(ds.target_revenue) / 4.0
            
            adjusted_target_orders = (remaining_orders_needed / days_remaining) * 91.25 if days_remaining > 0 else std_target_orders
            adjusted_target_revenue = (remaining_revenue_needed / days_remaining) * 91.25 if days_remaining > 0 else std_target_revenue
            
            # Actuals in current calendar quarter
            actual_orders_period = ConfirmedOrder.objects.filter(created_by__in=members, project_closing_date__range=(period_start, period_end)).count()
            actual_revenue_period_val = ConfirmedOrder.objects.filter(created_by__in=members, project_closing_date__range=(period_start, period_end)).aggregate(total_rev=Sum('quotation__finalamount'))['total_rev'] or 0
            actual_revenue_period = float(actual_revenue_period_val)
            
        else: # yearly
            std_target_orders = ds.target_orders
            std_target_revenue = float(ds.target_revenue)
            
            adjusted_target_orders = ds.target_orders
            adjusted_target_revenue = float(ds.target_revenue)
            
            actual_orders_period = ConfirmedOrder.objects.filter(created_by__in=members, project_closing_date__range=(start_date, end_date)).count()
            actual_revenue_period_val = ConfirmedOrder.objects.filter(created_by__in=members, project_closing_date__range=(start_date, end_date)).aggregate(total_rev=Sum('quotation__finalamount'))['total_rev'] or 0
            actual_revenue_period = float(actual_revenue_period_val)

        # Status: On track if overall YTD performance is ahead of YTD target
        status = "On Track"
        if actual_orders_ytd < expected_orders_ytd or actual_revenue_ytd < expected_revenue_ytd:
            status = "Off Track"

        # Determine target shortfall (how much behind they are overall)
        orders_shortfall = max(0, round(expected_orders_ytd - actual_orders_ytd, 1))
        revenue_shortfall = max(0.0, round(expected_revenue_ytd - actual_revenue_ytd, 2))

        dealerships_data.append({
            'dealership': ds,
            'actual_orders': actual_orders_period,
            'actual_revenue': actual_revenue_period,
            'target_orders': round(adjusted_target_orders, 1),
            'target_revenue': round(adjusted_target_revenue, 2),
            'std_target_orders': round(std_target_orders, 1),
            'std_target_revenue': round(std_target_revenue, 2),
            'status': status,
            'orders_shortfall': orders_shortfall,
            'revenue_shortfall': revenue_shortfall,
            'progress_orders': min(100.0, round((actual_orders_period / adjusted_target_orders * 100) if adjusted_target_orders > 0 else 0, 1)) if adjusted_target_orders > 0 else 0.0,
            'progress_revenue': min(100.0, round((actual_revenue_period / adjusted_target_revenue * 100) if adjusted_target_revenue > 0 else 0, 1)) if adjusted_target_revenue > 0 else 0.0,
        })

    # Funnel Dealership and User Filter
    selected_dealership_id = request.POST.get('dealership') if request.method == 'POST' else request.GET.get('dealership', 'all')
    selected_user_id = request.POST.get('user') if request.method == 'POST' else request.GET.get('user', 'all')
    
    if selected_dealership_id != 'all':
        try:
            selected_dealership = Dealership.objects.get(id=selected_dealership_id)
            users_in_dealership = selected_dealership.members.all()
        except (Dealership.DoesNotExist, ValueError):
            selected_dealership = None
            selected_dealership_id = 'all'
            users_in_dealership = User.objects.all()
    else:
        selected_dealership = None
        users_in_dealership = User.objects.all()

    if selected_user_id == 'all':
        selected_user = None
        base_enquiries = Enquiry.objects.filter(created_by__in=users_in_dealership)
        base_confirmed = ConfirmedOrder.objects.filter(created_by__in=users_in_dealership)
    else:
        try:
            selected_user = User.objects.get(id=selected_user_id)
            selected_user_id = str(selected_user.id)
            base_enquiries = Enquiry.objects.filter(created_by=selected_user)
            base_confirmed = ConfirmedOrder.objects.filter(created_by=selected_user)
        except (User.DoesNotExist, ValueError):
            selected_user = None
            selected_user_id = 'all'
            base_enquiries = Enquiry.objects.filter(created_by__in=users_in_dealership)
            base_confirmed = ConfirmedOrder.objects.filter(created_by__in=users_in_dealership)

    funnel_enquiry_count = base_enquiries.filter(is_lost=False, is_confirmed=False).count()
    funnel_quotation_count = base_enquiries.filter(quotation__isnull=False, is_lost=False, is_confirmed=False).distinct().count()
    funnel_confirmed_count = base_confirmed.count()
    funnel_lost_count = base_enquiries.filter(is_lost=True).count()

    context = {
        'is_manager': is_manager,
        'dealerships_data': dealerships_data,
        'view_mode': view_mode,
        'users': users_in_dealership,
        'selected_user': selected_user,
        'selected_user_id': selected_user_id,
        'all_dealerships': all_dealerships,
        'selected_dealership_id': selected_dealership_id,
        'funnel_enquiry_count': funnel_enquiry_count,
        'funnel_quotation_count': funnel_quotation_count,
        'funnel_confirmed_count': funnel_confirmed_count,
        'funnel_lost_count': funnel_lost_count,
    }
    return render(request, 'xp2/dealership_dashboard.html', context)


from django.contrib import messages
from django.http import HttpResponseForbidden

def manage_dealerships(request):
    current_user = request.user
    has_profile = hasattr(current_user, 'userprofile')
    is_xpredict = has_profile and current_user.userprofile.is_xpredict
    
    if not (current_user.is_superuser or current_user.is_staff or is_xpredict):
        return HttpResponseForbidden("You do not have permission to access this page.")
        
    dealerships = Dealership.objects.all()
    all_users = User.objects.all().order_by('username')
    zones = Zone.objects.all().order_by('name')
    divisions = Division.objects.all().order_by('name')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        start_date = request.POST.get('start_date') or None
        end_date = request.POST.get('end_date') or None
        target_orders = int(request.POST.get('target_orders', 0) or 0)
        target_revenue = float(request.POST.get('target_revenue', 0.0) or 0.0)
        member_ids = request.POST.getlist('members')
        
        dealership = Dealership.objects.create(
            name=name,
            start_date=start_date,
            end_date=end_date,
            target_orders=target_orders,
            target_revenue=target_revenue
        )
        dealership.members.set(member_ids)
        messages.success(request, f"Dealership '{name}' created successfully!")
        return redirect('manage_dealerships')
        
    return render(request, 'xp2/manage_dealerships.html', {
        'dealerships': dealerships,
        'all_users': all_users,
        'zones': zones,
        'divisions': divisions,
    })

def create_dealership_user(request, dealership_id):
    current_user = request.user
    has_profile = hasattr(current_user, 'userprofile')
    is_xpredict = has_profile and current_user.userprofile.is_xpredict
    
    if not (current_user.is_superuser or current_user.is_staff or is_xpredict):
        return HttpResponseForbidden("You do not have permission to perform this action.")
        
    dealership = get_object_or_404(Dealership, id=dealership_id)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        contact_number = request.POST.get('contact_number', '0000000000') or '0000000000'
        date_of_birth = request.POST.get('date_of_birth') or '2000-01-01'
        zone_id = request.POST.get('zone')
        division_id = request.POST.get('division')
        is_xpredict_val = request.POST.get('is_xpredict') == 'on'
        
        # Validation
        if User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' already exists.")
            return redirect('manage_dealerships')
            
        if User.objects.filter(email=email).exists() or UserProfile.objects.filter(email=email).exists():
            messages.error(request, f"A user with email '{email}' already exists.")
            return redirect('manage_dealerships')
            
        # Create User
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        
        # Resolve Zone and Division
        zone = Zone.objects.filter(id=zone_id).first() if zone_id else None
        division = Division.objects.filter(id=division_id).first() if division_id else None
        
        # Create UserProfile
        UserProfile.objects.create(
            user=user,
            email=email,
            contact_number=contact_number,
            date_of_birth=date_of_birth,
            zone=zone,
            division=division,
            is_xpredict=is_xpredict_val
        )
        
        # Add the user to the Dealership
        dealership.members.add(user)
        
        messages.success(request, f"User '{username}' created and assigned to '{dealership.name}' successfully!")
        
    return redirect('manage_dealerships')

def edit_dealership(request, dealership_id):
    current_user = request.user
    has_profile = hasattr(current_user, 'userprofile')
    is_xpredict = has_profile and current_user.userprofile.is_xpredict
    
    if not (current_user.is_superuser or current_user.is_staff or is_xpredict):
        return HttpResponseForbidden("You do not have permission to access this page.")
        
    dealership = get_object_or_404(Dealership, id=dealership_id)
    all_users = User.objects.all().order_by('username')
    
    if request.method == 'POST':
        dealership.name = request.POST.get('name')
        dealership.start_date = request.POST.get('start_date') or None
        dealership.end_date = request.POST.get('end_date') or None
        dealership.target_orders = int(request.POST.get('target_orders', 0) or 0)
        dealership.target_revenue = float(request.POST.get('target_revenue', 0.0) or 0.0)
        
        member_ids = request.POST.getlist('members')
        dealership.members.set(member_ids)
        dealership.save()
        
        messages.success(request, f"Dealership '{dealership.name}' updated successfully!")
        return redirect('manage_dealerships')
        
    return render(request, 'xp2/edit_dealership.html', {
        'dealership': dealership,
        'all_users': all_users,
        'current_members': dealership.members.all(),
    })

def manage_dealership_pricing(request, dealership_id):
    current_user = request.user
    has_profile = hasattr(current_user, 'userprofile')
    is_xpredict = has_profile and current_user.userprofile.is_xpredict
    
    if not (current_user.is_superuser or current_user.is_staff or is_xpredict):
        return HttpResponseForbidden("You do not have permission to access this page.")
        
    dealership = get_object_or_404(Dealership, id=dealership_id)
    products = Products.objects.all()
    
    # Fetch existing pricing
    existing_pricing = {dp.product_id: dp for dp in DealershipPricing.objects.filter(dealership=dealership)}
    
    if request.method == 'POST':
        # Loop through products and save prices
        for product in products:
            transfer_price_val = request.POST.get(f'transfer_price_{product.id}', '0.00')
            max_price_val = request.POST.get(f'max_price_{product.id}', '0.00')
            
            transfer_price = float(transfer_price_val) if transfer_price_val else 0.00
            max_price = float(max_price_val) if max_price_val else 0.00
            
            # Save or Update DealershipPricing
            DealershipPricing.objects.update_or_create(
                dealership=dealership,
                product=product,
                defaults={
                    'transfer_price': transfer_price,
                    'max_price': max_price
                }
            )
            
        messages.success(request, f"Product pricing for '{dealership.name}' updated successfully!")
        return redirect('manage_dealerships')
        
    pricing_list = []
    for product in products:
        pricing = existing_pricing.get(product.id)
        pricing_list.append({
            'product': product,
            'transfer_price': pricing.transfer_price if pricing else 0.00,
            'max_price': pricing.max_price if pricing else 0.00,
        })
        
    return render(request, 'xp2/manage_dealership_pricing.html', {
        'dealership': dealership,
        'pricing_list': pricing_list,
    })


from datetime import datetime
from django.shortcuts import render
from .models import quotation, Enquiry,Xpredict,BankDetails,CommercialQuote,QuotationItem

from django.core.serializers import serialize



from django.db.models import Max

from django.core.mail import send_mail
from django.conf import settings
from .models import Dealership

def send_price_limit_alert(user, product, unit_price, limits):
    subject = f"Price Limit Exceeded Alert: {user.username} on {product.name}"
    message = (
        f"Dealer: {user.username}\n"
        f"Product: {product.name}\n"
        f"Attempted Unit Price: {unit_price}\n"
        f"Allowed Limits: Transfer Price = {limits['transfer_price']}, Max Price = {limits['max_price']}\n\n"
        f"Please review this quotation."
    )
    # Send to all Xpredict team members
    from app.models import UserProfile
    xpredict_users = UserProfile.objects.filter(is_xpredict=True).select_related('user')
    recipient_list = [up.user.email for up in xpredict_users if up.user.email]
    
    if not recipient_list:
        # Fallback to admins if no xpredict users have email
        recipient_list = [admin[1] for admin in settings.ADMINS] if settings.ADMINS else []
        
    if recipient_list:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list, fail_silently=True)

def create_commercial_quote(request, enquiry_id):
    # Fetch the bank details and other necessary data
    banks = BankDetails.objects.all()
    xpredict_data = Xpredict.objects.first()
    products = Products.objects.all()
    enquiry = Enquiry.objects.get(id=enquiry_id)

    user_dealerships = request.user.dealerships.all()
    pricing_map = {}
    is_dealer = False

    if user_dealerships.exists():
        is_dealer = True
        dealership = user_dealerships.first()
        from .models import DealershipPricing
        dealership_pricings = DealershipPricing.objects.filter(dealership=dealership)
        for dp in dealership_pricings:
            pricing_map[dp.product.id] = {
                'transfer_price': float(dp.transfer_price),
                'max_price': float(dp.max_price)
            }

    # Generate the quotation number
    current_year_month = datetime.now().strftime('%y%m')

    # Find the last quotation number globally
    last_quotation = CommercialQuote.objects.aggregate(Max('id'))['id__max']
    if last_quotation:
        next_number = str(last_quotation + 1).zfill(3)  # Increment the last quotation ID and pad with zeros
    else:
        next_number = '001'  # Start from 001 if no records exist

    quotation_no = f'EL-HID-CM-{current_year_month}{next_number}'

    # Handle form submission to save data in the model
    if request.method == 'POST':
        print("POST Data Received:")
        for key, value in request.POST.items():
            print(f"{key}: {value}")
        # Extract all relevant data from the form

        bill_to_company_name = request.POST.get('bill_to_company_name')
        bill_to_customer_name = request.POST.get('bill_to_customer_name')
        bill_to_gst_number = request.POST.get('bill_to_gst_number')
        bill_to_address = request.POST.get('bill_to_address')
        ship_to_company_name = request.POST.get('ship_to_company_name')
        ship_to_customer_name = request.POST.get('ship_to_customer_name')
        ship_to_gst_number = request.POST.get('ship_to_gst_number')
        ship_to_address = request.POST.get('ship_to_address')
        from_company_name = request.POST.get('from_company_name')
        from_phone = request.POST.get('from_phone')
        from_email = request.POST.get('from_email')
        from_gst = request.POST.get('from_gst')
        from_pan = request.POST.get('from_pan')
        from_address = request.POST.get('from_address')
        subtotal = request.POST.get('subtotal', 0)
        cgst_total = request.POST.get('cgst_total', 0)
        sgst_total = request.POST.get('sgst_total', 0)
        igst_total = request.POST.get('igst_total', 0)
        grand_total = request.POST.get('grand_total', 0)
        
        # Handle bank selection
        bank_id = request.POST.get('bank_id')  # This would be the selected bank ID from the form
        terms_and_conditions = request.POST.get('terms_and_conditions')

        # Ensure the bank_id is valid (check if it's not empty or None)
        if not bank_id:
            # Handle the error, for example, by returning a message
            return render(request, 'xp2/commercial_quote.html', {
                'error': 'Please select a bank',
                'enquiry_id': enquiry_id,
                'quotation_no': quotation_no,
                'enquiry': enquiry,
                'form': EnquiryForm(instance=enquiry),
                'products': products,
                'xpredict': xpredict_data,
                'banks': banks,
            })

        # Fetch the bank instance from the database
        try:
            bank = BankDetails.objects.get(id=bank_id)
        except BankDetails.DoesNotExist:
            return render(request, 'xp2/commercial_quote.html', {
                'error': 'Invalid bank selection',
                'enquiry_id': enquiry_id,
                'quotation_no': quotation_no,
                'enquiry': enquiry,
                'form': EnquiryForm(instance=enquiry),
                'products': products,
                'xpredict': xpredict_data,
                'banks': banks,
            })  

        # Create a new CommercialQuote instance and save it to the database
        commercial_quote = CommercialQuote(
            enquiry_id=enquiry_id,
            quotation_no=quotation_no,
            bill_to_company_name=bill_to_company_name,
            bill_to_customer_name=bill_to_customer_name,
            bill_to_gst_number=bill_to_gst_number,
            bill_to_address=bill_to_address,
            ship_to_company_name=ship_to_company_name,
            ship_to_customer_name=ship_to_customer_name,
            ship_to_gst_number=ship_to_gst_number,
            ship_to_address=ship_to_address,
            from_company_name=from_company_name,
            from_phone=from_phone,
            from_email=from_email,
            from_gst=from_gst,
            from_pan=from_pan,
            from_address=from_address,
            bank=bank, 
            terms_and_conditions=terms_and_conditions,
            subtotal=subtotal,
            cgst_total=cgst_total,
            sgst_total=sgst_total,
            igst_total=igst_total,
            grand_total=grand_total,
        )
        commercial_quote.save()

        products_selected = request.POST.getlist('products[]')
        hsn_codes = request.POST.getlist('hsncode[]')
        base_amounts = request.POST.getlist('base_amount[]')
        quantities = request.POST.getlist('quantity[]')
        margins = request.POST.getlist('margin[]')
        cgsts = request.POST.getlist('cgst[]')
        sgsts = request.POST.getlist('sgst[]')
        igsts = request.POST.getlist('igst[]')
        final_amounts = request.POST.getlist('final_amount[]')

     
        # Ensure that the primary lists have equal length
        if not (len(products_selected) == len(hsn_codes) == len(base_amounts) == len(quantities) == len(margins) == len(final_amounts)):
            raise ValueError("Mismatch in the number of products and other item details")

        # Handle missing CGST/SGST/IGST values
        if not cgsts:
            cgsts = ['0'] * len(products_selected)
        if not sgsts:
            sgsts = ['0'] * len(products_selected)
        if not igsts:
            igsts = ['0'] * len(products_selected)

        # Pre-process product IDs (resolving/creating products for custom names)
        product_ids = []
        for i, product_name in enumerate(products_selected):
            product_name = product_name.strip()
            hsncode = hsn_codes[i].strip() if i < len(hsn_codes) else ""
            base_amount = base_amounts[i] if i < len(base_amounts) else 0
            gst = (
                float(cgsts[i] or 0) + float(sgsts[i] or 0) + float(igsts[i] or 0)
                if i < len(cgsts) and i < len(sgsts) and i < len(igsts)
                else 0
            )

            if product_name.isdigit():
                product_ids.append(product_name)
                continue

            # Create or get the product
            product, created = Products.objects.get_or_create(
                name=product_name,
                defaults={
                    "hsncode": hsncode,
                    "base_amount": base_amount,
                    "gst": gst,
                },
            )

            if not created:
                product.hsncode = hsncode
                product.base_amount = base_amount
                product.gst = gst
                product.save()

            product_ids.append(str(product.id))

        total_dealer_margin = 0.0
        # Loop through the selected items and create QuotationItem for each one
        for i in range(len(product_ids)):
            try:
                product_id = product_ids[i]
                product = Products.objects.get(id=product_id)
                hsn_code = hsn_codes[i]
                base_amount = float(base_amounts[i] or 0)
                quantity = int(quantities[i] or 0)
                margin = float(margins[i] or 0)
                final_amount = float(final_amounts[i] or 0)

                # Ensure rate is calculated correctly
                rate = (base_amount * quantity) * (1 + margin / 100)
                unit_price = base_amount * (1 + margin / 100)

                transfer_price = 0.00
                if is_dealer and product.id in pricing_map:
                    limits = pricing_map[product.id]
                    transfer_price = float(limits['transfer_price'])
                    if unit_price < limits['transfer_price'] or unit_price > limits['max_price']:
                        send_price_limit_alert(request.user, product, unit_price, limits)

                # Calculate dealer margin for this item
                item_margin = (unit_price - transfer_price) * quantity
                total_dealer_margin += item_margin

                # Get the GST values for the current product
                cgst = float(cgsts[i]) if cgsts[i] else 0.0
                sgst = float(sgsts[i]) if sgsts[i] else 0.0
                igst = float(igsts[i]) if igsts[i] else 0.0

                # Create and save QuotationItem
                quotation_item = QuotationItem(
                    quotation_no=quotation_no,
                    product=product,
                    hsncode=hsn_code,
                    base_amount=base_amount,
                    quantity=quantity,
                    margin=margin,
                    rate=rate,
                    cgst=cgst,
                    sgst=sgst,
                    igst=igst,
                    final_amount=final_amount,
                    transfer_price=transfer_price,
                    dealer_margin=item_margin,
                )
                quotation_item.save()

            except IndexError as e:
                print(f"Index error at {i}: {e}")
                raise e
            except Exception as e:
                print(f"Error saving quotation item at index {i}: {e}")
                raise e

        # Save total dealer margin on the quote
        commercial_quote.dealer_margin = total_dealer_margin
        commercial_quote.save()

        return redirect('managequotationpage', enquiry_id=enquiry_id)  # Redirect after saving the quote

    else:
        form = EnquiryForm(instance=enquiry)

    # Pass the data to the template
    bank_data = serialize('json', banks)

    import json
    pricing_map_json = json.dumps(pricing_map)

    return render(request, 'xp2/commercial_quote.html', {
        'enquiry_id': enquiry_id,
        'quotation_no': quotation_no,
        'enquiry': enquiry,
        'form': form,
        'products': products,
        'xpredict': xpredict_data,
        'banks': banks,
        'bank_data': bank_data,
        'pricing_map_json': pricing_map_json,
        'is_dealer': is_dealer,
    })

def generate_quote(request, enquiry_id, quote_type):
    # Fetch all previous data related to this enquiry and quote_type
    saved_data = SaveQuoteData.objects.filter(enquiry_id=enquiry_id, quote_type=quote_type).order_by('-id').first()
    enquiry = get_object_or_404(Enquiry, id=enquiry_id)

    print("Fetched Saved Data in `generate_quote`:", saved_data)
    print("Items associated:", saved_data.items.all() if saved_data else "None")

    if not saved_data:
        return redirect('manage_quotation', enquiry_id=enquiry_id)

    # Convert numeric fields properly, fallback to 0.00 if None
    total_taxable_value = float(saved_data.total_taxable_value or 0.00)
    cgst_amount = float(saved_data.cgst_amount or 0.00)
    sgst_amount = float(saved_data.sgst_amount or 0.00)
    igst_amount = float(saved_data.igst_amount or 0.00)

    # Determine CGST/SGST/IGST breakdown
    is_igst = igst_amount > 0
    is_cgst_sgst = cgst_amount > 0 or sgst_amount > 0

    return render(request, 'xp2/commercial_quote.html', {
        'enquiry': enquiry,
        'saved_data': saved_data,
        'is_igst': is_igst,
        'is_cgst_sgst': is_cgst_sgst,
    })


@login_required
def potential_duplicates(request):
    current_user = request.user
    has_profile = hasattr(current_user, 'userprofile')
    is_xpredict = has_profile and current_user.userprofile.is_xpredict
    
    if not (current_user.is_superuser or current_user.is_staff or is_xpredict):
        return HttpResponseForbidden("You do not have permission to access this page.")
        
    # Find all enquiries with the flag in remarks
    duplicates = Enquiry.objects.filter(remarks__icontains="[SYSTEM FLAG: POTENTIAL DUPLICATE OF ENQ ID").order_by('-created_at')
    
    duplicate_pairs = []
    import re
    
    for dup in duplicates:
        # Extract the ID from the remarks string
        match = re.search(r"POTENTIAL DUPLICATE OF ENQ ID (\d+)", dup.remarks)
        if match:
            target_id = match.group(1)
            try:
                target_enquiry = Enquiry.objects.get(id=target_id)
                duplicate_pairs.append({
                    'target': target_enquiry,
                    'duplicate': dup
                })
            except Enquiry.DoesNotExist:
                # The target was probably deleted, keep the pair with target=None or ignore
                pass

    return render(request, 'xp2/potential_duplicates.html', {
        'duplicate_pairs': duplicate_pairs,
    })


@login_required
def merge_enquiry(request, duplicate_id, target_id):
    import re
    current_user = request.user
    has_profile = hasattr(current_user, 'userprofile')
    is_xpredict = has_profile and current_user.userprofile.is_xpredict
    
    if not (current_user.is_superuser or current_user.is_staff or is_xpredict):
        return HttpResponseForbidden("You do not have permission to perform this action.")
        
    if request.method == "POST":
        action = request.POST.get("action")
        
        try:
            duplicate = Enquiry.objects.get(id=duplicate_id)
            target = Enquiry.objects.get(id=target_id)
            
            if action == "merge":
                # Move FollowUps
                FollowUp.objects.filter(enquiry=duplicate).update(enquiry=target)
                
                # Move UploadedQuotes
                UploadedQuote.objects.filter(enquiry=duplicate).update(enquiry=target)
                
                # Move FileUploadModel (ManyToMany)
                for file_obj in duplicate.files.all():
                    target.files.add(file_obj)
                    
                # Append Remarks
                if duplicate.remarks:
                    # Remove the system flag from duplicate
                    clean_remarks = re.sub(r"\n\n\[SYSTEM FLAG: POTENTIAL DUPLICATE OF ENQ ID \d+\]", "", duplicate.remarks)
                    if clean_remarks.strip():
                        target.remarks = f"{target.remarks or ''}\n--- Merged Remarks from Duplicate ---\n{clean_remarks}"
                        
                # Ensure target is also cleaned of flags (important for reverse merging)
                if target.remarks:
                    target.remarks = re.sub(r"\n\n\[SYSTEM FLAG: POTENTIAL DUPLICATE OF ENQ ID \d+\]", "", target.remarks)
                target.save()
                        
                # Delete duplicate
                duplicate.delete()
                messages.success(request, f"Successfully merged {duplicate.companyname} into Enquiry ID {target.id}.")
                
            elif action == "keep_separate":
                # Remove the flag from remarks
                import re
                clean_remarks = re.sub(r"\n\n\[SYSTEM FLAG: POTENTIAL DUPLICATE OF ENQ ID \d+\]", "", duplicate.remarks)
                duplicate.remarks = clean_remarks
                duplicate.save()
                messages.success(request, f"Duplicate flag removed for {duplicate.companyname}.")
                
        except Exception as e:
            messages.error(request, f"Error resolving duplicate: {str(e)}")
            
    return redirect('potential_duplicates')

    return render(request, 'xp2/commercial_quote.html', {
        'enquiry_id': enquiry_id,
        'quotation_no': quotation_no,
        'enquiry': enquiry,
        'form': form,
        'products': products,
        'xpredict': xpredict_data,
        'banks': banks,  # Pass the bank objects to the template
        'bank_data': bank_data,  # Pass serialized bank data to JS
        'is_dealer': is_dealer,
        'pricing_map_json': pricing_map_json,
    })


from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Max
from django.db import transaction
from .models import CommercialQuote, QuotationItem, Products, BankDetails, Xpredict

def Edit_commercial_quote(request, quotation_no):
    commercial_quote = get_object_or_404(CommercialQuote, quotation_no=quotation_no)
    banks = BankDetails.objects.all()
    xpredict_data = Xpredict.objects.all()
    products = Products.objects.all()
    quotation_items = QuotationItem.objects.filter(quotation_no=commercial_quote.quotation_no)
    
    user_dealerships = request.user.dealerships.all()
    pricing_map = {}
    is_dealer = False

    if user_dealerships.exists():
        is_dealer = True
        dealership = user_dealerships.first()
        from .models import DealershipPricing
        dealership_pricings = DealershipPricing.objects.filter(dealership=dealership)
        for dp in dealership_pricings:
            pricing_map[dp.product.id] = {
                'transfer_price': float(dp.transfer_price),
                'max_price': float(dp.max_price)
            }
    
    # Extract base quotation number before any -R revision suffix
    base_quotation_no = commercial_quote.quotation_no.split('-R')[0]
    last_revision = CommercialQuote.objects.filter(quotation_no__startswith=base_quotation_no).aggregate(Max('quotation_no'))
    last_quotation_no = last_revision['quotation_no__max']
    
    # Determine the next revision number
    if last_quotation_no and '-R' in last_quotation_no:
        next_revision = str(int(last_quotation_no.split('-R')[-1]) + 1)
    else:
        next_revision = "1"  # First revision
    
    new_quotation_no = f"{base_quotation_no}-R{next_revision}"
    print(f"🔢 New Quotation Number: {new_quotation_no}")
    
    if request.method == 'POST':
        print(request.POST.dict())  # Print POST data as a dictionary

        try:
            with transaction.atomic():
                print("🚀 Creating New Quotation Record...")
                bank_id = request.POST.get('bank_id')  
                if bank_id:
                    print("bank id ide ")
                    bank = BankDetails.objects.get(id=bank_id)  # Ensure the bank exists
                else:
                    print("bank id illa")

                # Create a new commercial quote record (instead of updating the existing one)
                new_commercial_quote = CommercialQuote.objects.create(
                    quotation_no=new_quotation_no,
                    bill_to_company_name=request.POST.get('bill_to_company_name'),
                    bill_to_customer_name=request.POST.get('bill_to_customer_name'),
                    bill_to_gst_number=request.POST.get('bill_to_gst_number'),
                    bill_to_address=request.POST.get('bill_to_address'),
                    ship_to_company_name=request.POST.get('ship_to_company_name'),
                    ship_to_customer_name=request.POST.get('ship_to_customer_name'),
                    ship_to_gst_number=request.POST.get('ship_to_gst_number'),
                    ship_to_address=request.POST.get('ship_to_address'),
                    from_company_name=request.POST.get('from_company_name'),
                    from_phone=request.POST.get('from_phone'),
                    from_email=request.POST.get('from_email'),
                    from_gst=request.POST.get('from_gst'),
                    from_pan=request.POST.get('from_pan'),
                    from_address=request.POST.get('from_address'),
                    terms_and_conditions=request.POST.get('terms_and_conditions'),
                    subtotal=request.POST.get('subtotal', 0),
                    cgst_total=request.POST.get('cgst_total', 0),
                    sgst_total=request.POST.get('sgst_total', 0),
                    igst_total=request.POST.get('igst_total', 0),
                    grand_total=request.POST.get('grand_total', 0),
                    bank = bank,
                    enquiry_id=commercial_quote.enquiry_id  # Retaining the same enquiry reference
                )
                print(f"✅ New Quotation Created: {new_commercial_quote.quotation_no}")
                
                # Fetch product data from form
                products_selected = request.POST.getlist('products[]')
                hsn_codes = request.POST.getlist('hsncode[]')
                base_amounts = request.POST.getlist('base_amount[]')
                quantities = request.POST.getlist('quantity[]')
                margins = request.POST.getlist('margin[]')
                rates = request.POST.getlist('rate[]')  # ✅ Include rate
                cgsts = request.POST.getlist('cgst[]')
                sgsts = request.POST.getlist('sgst[]')
                igsts = request.POST.getlist('igst[]')
                final_amounts = request.POST.getlist('final_amount[]')
                print("prod :",products_selected)
                print("hsn_codes :",hsn_codes)
                print("🔹 Initial Product selected:", products_selected)
                product_ids = []  # List to store product IDs instead of names

                for i, product_name in enumerate(products_selected):
                    product_name = product_name.strip()
                    hsncode = hsn_codes[i].strip() if i < len(hsn_codes) else ""
                    base_amount = base_amounts[i] if i < len(base_amounts) else 0
                    gst = (
                        float(cgsts[i] or 0) + float(sgsts[i] or 0) + float(igsts[i] or 0)
                        if i < len(cgsts) and i < len(sgsts) and i < len(igsts)
                        else 0
                    )

                    print("Processing:", product_name, "Type:", type(product_name))

                    # If `product_name` is an ID (digits only), append and continue
                    if product_name.isdigit():
                        product_ids.append(product_name)
                        print("appended:", product_name)
                        print("✅ This is an ID, skipping creation. and appending to product ids")
                        continue  

                    print("🆕 Creating new product:", product_name)

                    # Create or get the product
                    product, created = Products.objects.get_or_create(
                        name=product_name,
                        defaults={
                            "hsncode": hsncode,
                            "base_amount": base_amount,
                            "gst": gst,
                        },
                    )

                    if created:
                        print(f"✅ New product added: {product.name} with HSN: {hsncode}, Base Amount: {base_amount}, GST: {gst}")
                    else:
                        print(f"ℹ️ Existing product updated: {product.name}")
                        product.hsncode = hsncode
                        product.base_amount = base_amount
                        product.gst = gst
                        product.save()

                    # ✅ Always use the actual product.id, not the manually typed string
                    product_ids.append(str(product.id))

                print("🔹 Updated Product ID List:", product_ids)




                if product_ids:
                    total_items = len(product_ids)
                    print(f"🧾 Saving {total_items} Quotation Items...")
                    total_dealer_margin = 0.0

                    for i in range(total_items):
                        try:
                            product_id = product_ids[i]
                            print(f"🔍 Looking up Product ID: {product_id}")

                            product = Products.objects.get(id=product_id)

                            hsn = hsn_codes[i] if i < len(hsn_codes) else ''
                            base_amt = float(base_amounts[i]) if i < len(base_amounts) and base_amounts[i] else 0
                            qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 0
                            margin = float(margins[i]) if i < len(margins) and margins[i] else 0
                            rate = float(rates[i]) if i < len(rates) and rates[i] else 0
                            cgst = float(cgsts[i]) if i < len(cgsts) and cgsts[i] else 0
                            sgst = float(sgsts[i]) if i < len(sgsts) and sgsts[i] else 0
                            igst = float(igsts[i]) if i < len(igsts) and igsts[i] else 0
                            final_amt = float(final_amounts[i]) if i < len(final_amounts) and final_amounts[i] else 0

                            print(f"🧾 Creating QuotationItem for Product ID: {product_id} => {product.name}")
                            print(f" - HSN: {hsn}, Qty: {qty}, Margin: {margin}, Rate: {rate}")
                            print(f" - CGST: {cgst}, SGST: {sgst}, IGST: {igst}, Final: {final_amt}")

                            # Perform backend price limit validation for Dealers
                            unit_price = base_amt * (1 + margin / 100)
                            transfer_price = 0.00
                            if is_dealer and product.id in pricing_map:
                                limits = pricing_map[product.id]
                                transfer_price = float(limits['transfer_price'])
                                if unit_price < limits['transfer_price'] or unit_price > limits['max_price']:
                                    send_price_limit_alert(request.user, product, unit_price, limits)

                            item_margin = (unit_price - transfer_price) * qty
                            total_dealer_margin += item_margin

                            QuotationItem.objects.create(
                                quotation_no=new_commercial_quote.quotation_no,
                                product=product,
                                hsncode=hsn,
                                base_amount=base_amt,
                                quantity=qty,
                                margin=margin,
                                rate=rate,
                                cgst=cgst,
                                sgst=sgst,
                                igst=igst,
                                final_amount=final_amt,
                                transfer_price=transfer_price,
                                dealer_margin=item_margin,
                            )

                            print(f"✅ Quotation Item Saved: {product.name} (ID: {product_id})")

                        except Exception as e:
                            print(f"❌ Error saving product at index {i}: {e}")
                            raise e

                    # Save total dealer margin on the quote
                    new_commercial_quote.dealer_margin = total_dealer_margin
                    new_commercial_quote.save()

                return redirect('managequotationpage', enquiry_id=commercial_quote.enquiry_id)

        except Exception as e:
            print(f"❌ Error: {e}")
            import json
            pricing_map_json = json.dumps(pricing_map)
            context = {
                'commercial_quote': commercial_quote,
                'quotation_items': quotation_items,
                'products': products,
                'xpredict': xpredict_data,
                'banks': banks,
                'new_quotation_no': new_quotation_no,
                'error': str(e),
                'is_dealer': is_dealer,
                'pricing_map_json': pricing_map_json,
            }
            return render(request, 'xp2/edit_commercial.html', context)
    
    # GET request rendering
    import json
    pricing_map_json = json.dumps(pricing_map)
    context = {
        'commercial_quote': commercial_quote,
        'quotation_items': quotation_items,
        'products': products,
        'xpredict': xpredict_data,
        'banks': banks,
        'new_quotation_no': new_quotation_no,
        'is_dealer': is_dealer,
        'pricing_map_json': pricing_map_json,
    }
    return render(request, 'xp2/edit_commercial.html', context)



from django.http import JsonResponse
from django.shortcuts import get_object_or_404

def get_bank_details(request, bank_id):
    # Fetch the bank details from the database
    bank = get_object_or_404(BankDetails, id=bank_id)

    # Prepare the data to be returned in JSON format
    bank_data = {
        'bank_name': bank.bank_name,
        'account_holder_name': bank.account_holder_name,
        'account_number': bank.account_number,
        'ifsc_code': bank.ifsc_code,
        'branch_name': bank.branch_name,
        'address': bank.address,
        'phone_number': bank.phone_number,
        'email': bank.email,
    }

    return JsonResponse(bank_data)

from num2words import num2words

from django.shortcuts import get_object_or_404, render
from num2words import num2words

import locale

def preview_quotation(request, quotation_no):
    locale.setlocale(locale.LC_ALL, 'en_IN.UTF-8')  # Set locale to Indian format
    current_date = datetime.now().strftime('%d %b, %Y')

    quotation = get_object_or_404(CommercialQuote, quotation_no=quotation_no)
    quotation_items = QuotationItem.objects.filter(quotation_no=quotation_no)

    # Add unit price calculation for each item
    for item in quotation_items:
        item.unit_price = item.rate / item.quantity if item.quantity != 0 else 0

    # Format amounts
    formatted_subtotal = locale.format_string('%.2f', quotation.subtotal, grouping=True)
    formatted_cgst_total = locale.format_string('%.2f', quotation.cgst_total, grouping=True)
    formatted_sgst_total = locale.format_string('%.2f', quotation.sgst_total, grouping=True)
    formatted_igst_total = locale.format_string('%.2f', quotation.igst_total, grouping=True)
    formatted_grand_total = locale.format_string('%.2f', quotation.grand_total, grouping=True)

    # Convert grand total to Indian words
    grand_total_in_words = num2words(quotation.grand_total, lang='en_IN').replace(" and", "").replace(",", "").upper() + " RUPEES ONLY "

    context = {
        'quotation': quotation,
        'quotation_items': quotation_items,
        'subtotal': formatted_subtotal,
        'cgst_total': formatted_cgst_total,
        'sgst_total': formatted_sgst_total,
        'igst_total': formatted_igst_total,
        'grand_total': formatted_grand_total,
        'grand_total_in_words': grand_total_in_words,
        'current_date': current_date,
    }

    return render(request, 'xp2/quotation_preview.html', context)





def create_techno_commercial_quote(request, enquiry_id):
    # Logic for handling the techno-commercial quote creation
    return render(request, 'xp2/techno_commercial_quote.html', {'enquiry_id': enquiry_id,})

from django.http import Http404

from django.http import Http404
from num2words import num2words
import os
from datetime import datetime
from django.conf import settings
import json

def any_checked(items):
    """True if at least one dict in items has is_checked True."""
    if not items:
        return False
    for item in items:
        if item.get("is_checked", False):
            return True
    return False

def split_bullets(section):
    """
    Given a list of dicts with 'value' keys, splits any 'value' string by the bullet '•'
    and returns a list of points (strings), for checked items only.
    """
    result = []
    if not section:
        return result
    for item in section:
        if item.get("is_checked"):
            # Split by bullet (•), remove empty/whitespace, support accidental \r
            lines = [line.strip() for line in item.get("value", "").replace('\r','').split('•') if line.strip()]
            result.extend(lines)
    return result

def amc_preview(request, quotation_no):
    company = companydetails.objects.all()
    current_date = datetime.now().strftime('%d %b, %Y')

    base_dir = settings.BASE_DIR
    stored_data_dir = os.path.join(base_dir, 'stored_data')
    draft_data_dir = os.path.join(base_dir, 'AMC_draft')

    found_data = None
    draft_data = None

    # Check stored_data first
    for directory in os.listdir(stored_data_dir):
        dir_path = os.path.join(stored_data_dir, directory)
        if os.path.isdir(dir_path):
            file_path = os.path.join(dir_path, f"{quotation_no}.json")
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    try:
                        found_data = json.load(file)
                    except json.JSONDecodeError:
                        raise Http404(f"Invalid JSON file: {file_path}")
                break

    # Check draft_data if no stored data found
    if not found_data:
        for directory in os.listdir(draft_data_dir):
            dir_path = os.path.join(draft_data_dir, directory)
            if os.path.isdir(dir_path):
                file_path = os.path.join(dir_path, f"{quotation_no}.json")
                if os.path.exists(file_path):
                    with open(file_path, 'r') as file:
                        try:
                            draft_data = json.load(file)
                        except json.JSONDecodeError:
                            raise Http404(f"Invalid JSON file: {file_path}")
                    break

    if not found_data and not draft_data:
        raise Http404(f"Quotation with number {quotation_no} not found.")

    combined_data = found_data if found_data else draft_data

    # Safely fetch the value of 'value' inside 'Grand_Total'
    grand_total = combined_data.get('Grand_Total')
    if grand_total:
        gtotal_value = grand_total[0].get('value')
    else:
        gtotal_value = None

    if gtotal_value is not None:
        g_total_in_words = num2words(float(gtotal_value), lang='en_IN').replace(" and", "").replace(",", "").upper() + " RUPEES ONLY"
    else:
        g_total_in_words = "NONE"

    # Section show/hide flags and ready-to-loop pointwise lists for each section
    context = {
        'quotation_no': quotation_no,
        'data': combined_data,
        'current_date': current_date,
        'company': company,
        'g_total_in_words': g_total_in_words,
        "MEDIA_URL": settings.MEDIA_URL,
        'show_contents': any_checked(combined_data.get("contents")),
        'show_maintenance_support': any_checked(combined_data.get("maintenance_support")),
        'show_yearly_maintenance': any_checked(combined_data.get("yearly_maintenance")),
        'show_running_consumables': any_checked(combined_data.get("running_consumables")),
        'show_exclusions': any_checked(combined_data.get("exclusions")),
        'show_particulars': any_checked(combined_data.get("Particulars")),
        'show_terms': any_checked(combined_data.get("terms")),
        'maintenance_support_points': split_bullets(combined_data.get("maintenance_support")),
        'yearly_maintenance_points': split_bullets(combined_data.get("yearly_maintenance")),
        'running_consumables_points': split_bullets(combined_data.get("running_consumables")),
        'exclusions_points': split_bullets(combined_data.get("exclusions")),
        'terms_points': split_bullets(combined_data.get("terms")),
        'contents_points': [item['value'] for item in combined_data.get("contents", []) if item.get("is_checked")],
    }

    return render(request, 'xp2/amc_preview.html', context)

    





from .models import (
    QuotationProduct, QProduct, SpecTable, OutputTable, InstallationTable,
    StandardTable, Table1, ProcessDescription, Pricing, GeneralTermsAndConditions,
    Appendix, Contents, Proposal, Inclusions, ParticularsTable, AMC_Pricing,SpecificationTable
)
import logging
import os
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from datetime import datetime
import os
import json


from django.shortcuts import render

def preview(request, quotation_number):
    # Construct the file path based on the quotation number
    base_dir = settings.BASE_DIR
    file_path = os.path.join(base_dir, 'stored_data', f"{quotation_number}.json")

    # Check if the file exists and load the data
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            data = json.load(file)
    else:
        data = {'error': 'File not found'}

    # Pass the data to the template
    return render(request, 'xp2/preview.html', {'data': data})

from datetime import datetime
import os
import json

def get_quotation_number():
    storage_file = "quotation_number_store.json"
    current_year_month = datetime.now().strftime('%y%m')
    last_year_month = None
    last_sequential = 0

    if os.path.exists(storage_file):
        with open(storage_file, "r") as file:
            data = json.load(file)
            last_year_month = data.get("last_year_month")
            last_sequential = data.get("last_sequential", 0)
    if last_year_month != current_year_month:
        last_sequential = 0
    next_sequential = last_sequential + 1
    sequential_part = str(next_sequential).zfill(3)
    quotation_number = f"EL-HID-AMCPR-{current_year_month}{sequential_part}"
    with open(storage_file, "w") as file:
        json.dump({
            "last_year_month": current_year_month,
            "last_sequential": next_sequential
        }, file)
    return quotation_number

def amc_quotation_details(request, enquiry_id, product_id):
    try:
        enquiry = Enquiry.objects.get(id=enquiry_id)
    except Enquiry.DoesNotExist:
        return render(request, 'xp2/error_page.html', {'error': 'Enquiry not found'})

    products = QuotationProduct.objects.get(id=product_id)

    # --- Only generate quotation number once per session/draft ---
    if 'pending_quotation_number' not in request.session:
        request.session['pending_quotation_number'] = get_quotation_number()
    quotation_number = request.session['pending_quotation_number']

    particulars = ParticularsTable.objects.filter(pd_name=products)
    all_headers_particulars = {
        field.name: field.verbose_name.title() for field in ParticularsTable._meta.fields
    }
    excluded_fields_particulars = ['id', 'sl_no']  # Exclude fields
    headers = [
        header for field, header in all_headers_particulars.items()
        if field not in excluded_fields_particulars
    ]

    outputs = OutputTable.objects.filter(pd_name=products)
    contents = Contents.objects.filter(pd_name=products)
    amc_pricings = AMC_Pricing.objects.filter(pd_name=products)
    amc = amc_pricings.first()
    terms = amc.terms_conditions if amc else ''
    terms_and_conds = terms.split(".")
    installations = InstallationTable.objects.filter(pd_name=products)
    installation_count = installations.count()

    all_headers = {
        field.name: field.verbose_name.title() for field in InstallationTable._meta.fields
    }
    particulars = ParticularsTable.objects.filter(pd_name=products)
    all_headers_particulars = {
        field.name: field.verbose_name.title() for field in ParticularsTable._meta.fields
    }
    excluded_fields_particulars = ['id', 'sl_no', 'pd_name']
    headers_particulars = [
        header for field, header in all_headers_particulars.items()
        if field not in excluded_fields_particulars
    ]

    inclusion = Inclusions.objects.filter(pd_name=products).first()
    maintenance_text = inclusion.maintenance if inclusion else ''
    maintenance_text_year = inclusion.yearly_maintenance if inclusion else ''
    maintenance_text_run = inclusion.running_consumables if inclusion else ''
    maintenance_text_excl = inclusion.exclusions if inclusion else ''

    maintenance_lines = maintenance_text.split(".")
    maintenance_lines_year = maintenance_text_year.split(".")
    maintenance_lines_run = maintenance_text_run.split(".")
    maintenance_lines_excl = maintenance_text_excl.split(".")

    context = {
        'enquiry_id': enquiry_id,
        'maintenance_lines': maintenance_lines,
        'maintenance_lines_year': maintenance_lines_year,
        'maintenance_lines_run': maintenance_lines_run,
        'maintenance_lines_excl': maintenance_lines_excl,
        'products': products,
        'outputs': outputs,
        'particulars': particulars,
        'contents': contents,
        'installations': installations,
        'amc_pricings': amc_pricings,
        'headers': headers,
        'inclusion': inclusion,
        'headers_particulars': headers_particulars,
        'terms_and_conds': terms_and_conds,
        'quotation_number': quotation_number,
    }
    return render(request, 'xp2/amc_quotation_details.html', context)


def save_amc_quotation(request, enquiry_id, product_id):
    if request.method == "POST":
        # ... parse form data, validation, object creation etc. ...

        quotation_number = request.session.get('pending_quotation_number')
        # Save the new Quotation object, e.g.
        # Quotation.objects.create(number=quotation_number, ...)

        # After save, remove the reserved number to avoid reuse
        if 'pending_quotation_number' in request.session:
            del request.session['pending_quotation_number']

        # Redirect as appropriate
        return redirect("success_url_or_detail", enquiry_id=enquiry_id, product_id=product_id)

    # Optionally, render an error or redirect if GET
    return redirect("amc_quotation_details", enquiry_id=enquiry_id, product_id=product_id)




# ---------------------------------------------------STORING------------------------------------
# Logger setup
logger = logging.getLogger(__name__)

# Helper function to get current time for file naming
def now():
    return datetime.now()

@csrf_exempt
def store_data(request, enquiry_id, quotation_number):
    logger.info("Received request: %s", request.method)

    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Only POST requests are allowed"}, status=405
        )


    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse(
            {"status": "error", "message": "This request is not an AJAX request"},
            status=400,
        )

    try:
        # Handle FormData (request.POST and request.FILES)
        data = request.POST.dict()

        quotation_number = data.get("quotation_number")
        if not quotation_number:
            return JsonResponse(
                {"status": "error", "message": "Quotation number is missing"},
                status=400,
            )
        # Define base directory for the enquiry_id
        base_dir = os.path.join(settings.BASE_DIR, "stored_data", str(enquiry_id))
        os.makedirs(base_dir, exist_ok=True)
        file_path = os.path.join(base_dir, f"{quotation_number}.json")

        # Check if file already exists
        if os.path.exists(file_path):
            return JsonResponse(
                {"status": "error", "message": f"Quotation number {quotation_number} already exists for this enquiry"},
                status=400,
            )

        # Initialize lists to hold form data
        contents = []
        maintenance_support = []
        yearly_maintenance = []
        running_consumables = []
        Amc_Proposal = []
        exclusions = []
        amc_pricing = []
        Particulars = []
        Subtotal_list = []
        GST = []
        Grand_Total = []
        terms = []

        # Process each section of the form that has a checkbox
        # Contents Section
        for key in data.keys():
            if key.startswith("content_select_"):
                index = key.split("_")[-1]
                content_select_value = data.get(f"content_select_{index}")
                is_checked = content_select_value in ["1", "on", "true"]  # Adjust this comparison based on the actual values received
                content_value = data.get(f"content_{index}")
                if content_value:
                    contents.append({"value": content_value, "is_checked": is_checked})

        # Amc_Proposal (Installations) Section
        for key in data.keys():
            if key.startswith('select_amc_check_'):

                index = key.split('_')[-1]
                is_checked = data.get(f'select_amc_check_{index}') == "1"
                installation_data = {
                    'pd_name': data.get(f'pd_name_{index}'),
                    'capacity': data.get(f'capacity_{index}'),
                    'total_needed_capacity': data.get(f'total_needed_capacity_{index}'),
                    'waste_water_type': data.get(f'waste_water_type_{index}'),
                    'total_no_machines': data.get(f'total_no_machines_{index}'),
                    'is_checked': is_checked
                }
                Amc_Proposal.append(installation_data)
        # Inclusions Section
        for key in data.keys():
            if key.startswith("maintenance_support_check_"):
                index = key.split("_")[-1]
                is_checked = data.get(f"maintenance_support_check_{index}") == "1"
                maintenance_support_value = data.get(f"maintenance_support_{index}")
                if maintenance_support_value:
                    maintenance_support.append({"value": maintenance_support_value, "is_checked": is_checked})

        # Yearly Maintenance Section
        for key in data.keys():
            if key.startswith("yearly_maintenance_check_"):
                index = key.split("_")[-1]
                is_checked = data.get(f"yearly_maintenance_check_{index}") == "1"
                yearly_maintenance_value = data.get(f"yearly_maintenance_{index}")
                if yearly_maintenance_value:
                    yearly_maintenance.append({"value": yearly_maintenance_value, "is_checked": is_checked})

        # Running Consumables Section
        for key in data.keys():
            if key.startswith("running_consumables_check_"):
                index = key.split("_")[-1]
                is_checked = data.get(f"running_consumables_check_{index}") == "1"
                running_consumables_value = data.get(f"running_consumables_{index}")
                if running_consumables_value:
                    running_consumables.append({"value": running_consumables_value, "is_checked": is_checked})

        # Exclusions Section
        for key in data.keys():
            if key.startswith("exclusions_check_"):
                index = key.split("_")[-1]
                is_checked = data.get(f"exclusions_check_{index}") == "1"
                exclusions_value = data.get(f"exclusions_{index}")
                if exclusions_value:
                    exclusions.append({"value": exclusions_value, "is_checked": is_checked})
        # AMC Pricing Section
        for key in data.keys():
            if key.startswith('select_amcp_check_'):
                index = key.split('_')[-1]
                is_checked = data.get(f'select_amcp_check_{index}') == "1"
                installation_data = {
                    'pd_name': data.get(f'pd_namep_{index}'),
                    'capacity': data.get(f'capacityp_{index}'),
                    'total_needed_capacity': data.get(f'total_needed_capacityp_{index}'),
                    'waste_water_type': data.get(f'waste_water_typep_{index}'),
                    'total_no_machines': data.get(f'total_no_machinesp_{index}'),
                    'is_checked': is_checked
                }
                amc_pricing.append(installation_data)
        for key in data.keys():
            if key.startswith('select_per_check_'):
                index = key.split('_')[-1]
                is_checked = data.get(f'select_per_check_{index}') == "1"
                installation_data = {
                    'particulars': data.get(f'particulars_{index}'),
                    'first_year_exgst': data.get(f'first_year_exgst_{index}'),
                    'is_checked': is_checked
                }
                Particulars.append(installation_data)

        # Terms Section
        for key in data.keys():
            if key.startswith("terms_check_"):
                index = key.split("_")[-1]
                is_checked = data.get(f"terms_check_{index}") == "1"
                terms_value = data.get(f"terms_{index}")
                if terms_value:
                    terms.append({"value": terms_value, "is_checked": is_checked})

        # Extract Subtotal
        if "content_select_sub" in data:
            is_checked = data.get("content_select_sub") == "on"  # Match "on" for checkbox behavior
            Subtotal_value = data.get("Subtotal1")
            if Subtotal_value:
                Subtotal_list.append({"value": Subtotal_value, "is_checked": is_checked})

        # Extract GST
        if "content_select_gst" in data:
            is_checked = data.get("content_select_gst") == "on"
            gst_value = data.get("gst1")
            if gst_value:
                GST.append({"value": gst_value, "is_checked": is_checked})

        # Extract Grand Total
        if "content_select_gtotal" in data:
            is_checked = data.get("content_select_gtotal") == "on"
            gtotal_value = data.get("grand")
            if gtotal_value:
                Grand_Total.append({"value": gtotal_value, "is_checked": is_checked})


        # Prepare the final data for saving
        final_data = {
            'quotation_number': quotation_number,
            'contents': contents,
            'terms': terms,
            'Amc_Proposal': Amc_Proposal,
            'maintenance_support': maintenance_support,
            'yearly_maintenance': yearly_maintenance,
            'running_consumables': running_consumables,
            'exclusions': exclusions,
            'amc_pricing': amc_pricing,
            'Particulars': Particulars,
            'Subtotal_list': Subtotal_list,
            'GST': GST,
            'Grand_Total': Grand_Total,
            'enquiry_id': enquiry_id,
        }

        # Store the final data in the file as JSON
        print(f"final",final_data)
        with open(file_path, "w") as json_file:
            json.dump(final_data, json_file, indent=4)
        logger.info("Data stored successfully at: %s", file_path)

        return JsonResponse(
            {"status": "success", "message": "Data stored successfully", "file_path": file_path}
        )

    except Exception as e:
        logger.error("An unexpected error occurred", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

    
    
    
##########################################################################################################################

from django.shortcuts import render
from django.http import JsonResponse
import os
import json
from django.conf import settings

def saved_quotations(request):
    try:
        base_dir = os.path.join(settings.BASE_DIR, "stored_data")
        quotations = []

        if os.path.exists(base_dir):
            for file_name in os.listdir(base_dir):
                if file_name.endswith(".json"):
                    file_path = os.path.join(base_dir, file_name)
                    with open(file_path, "r") as file:
                        data = json.load(file)
                        quotations.append({
                            "quotation_number": file_name.split(".")[0],
                        })

        return render(request, "xp2/amc_saved.html", {"quotations": quotations})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)




# -------------------------------------------edit quotation -----------------------
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import os
import json
import re

def slugify(txt):
    return re.sub(r'(^-|-$)', '', re.sub(r'[^a-z0-9]+', '-', txt.lower()))

@csrf_exempt
def edit_quotation(request, enquiry_id, quotation_number):
    import logging
    logger = logging.getLogger('django')  # If you want logging to work!
    logger.info("Editing Quotation: %s, %s", enquiry_id, quotation_number)

    # Define the file path for the existing quotation data (JSON file)
    file_path = os.path.join(settings.BASE_DIR, "stored_data", str(enquiry_id), f"{quotation_number}.json")
    print(f"path:",file_path)
    if not os.path.exists(file_path):
        return JsonResponse({"status": "error", "message": "Quotation not found"}, status=404)

    # Load existing data for GET and template prefill
    with open(file_path, "r") as json_file:
        quotation_data = json.load(json_file)

    # ----- AUTO-PREFILL PATCH START -----
    def ensure_section_row_if_checked(section_slug, data_key, row_template):
        checked = False
        for c in quotation_data.get('contents', []):
            value = c.get('value', '') if isinstance(c, dict) else ''
            slug = slugify(value.split('-------------------')[0]) if value else ''
            if slug == section_slug and (c.get('is_checked') if isinstance(c, dict) else False):
                checked = True
                break
        if checked and not quotation_data.get(data_key):
            quotation_data[data_key] = [row_template.copy()]

    ensure_section_row_if_checked(
        'amc-proposal', 'Amc_Proposal',
        {'pd_name': '', 'capacity': '', 'total_needed_capacity': '',
         'waste_water_type': '', 'total_no_machines': '', 'is_checked': False}
    )
    ensure_section_row_if_checked(
        'pricing-amc-for-one-year', 'amc_pricing',
        {'pd_name': '', 'capacity': '', 'total_needed_capacity': '',
         'waste_water_type': '', 'total_no_machines': '', 'is_checked': False}
    )
    ensure_section_row_if_checked(
        'inclusions-comprehensive-amc', 'maintenance_support',
        {'value': '', 'is_checked': False}
    )
    ensure_section_row_if_checked(
        'yearly-maintenance-and-upkeep', 'yearly_maintenance',
        {'value': '', 'is_checked': False}
    )
    ensure_section_row_if_checked(
        'running-consumables-and-chemicals-as-required', 'running_consumables',
        {'value': '', 'is_checked': False}
    )
    ensure_section_row_if_checked(
        'exclusions-comprehensive-amc', 'exclusions',
        {'value': '', 'is_checked': False}
    )
    # Add similar lines for any extra sections you have
    # ----- AUTO-PREFILL PATCH END -----

    if request.method == "POST":
        data = request.POST
        print(f"sent from template", data)
        contents = []
        maintenance_support = []
        yearly_maintenance = []
        running_consumables = []
        Amc_Proposal = []
        exclusions = []
        amc_pricing = []
        Particulars = []
        Subtotal_list = []
        GST = []
        Grand_Total = []
        terms = []
        try:
            for key in data.keys():
                if key.startswith("content_select_"):
                    index = key.split("_")[-1]
                    content_select_value = data.get(f"content_select_{index}")
                    is_checked = content_select_value in ["1", "on", "true"]
                    content_value = data.get(f"content_{index}")
                    if content_value:
                        contents.append({"value": content_value, "is_checked": is_checked})
            for key in data.keys():
                if key.startswith('select_amc_check_'):
                    index = key.split('_')[-1]
                    is_checked = data.get(f'select_amc_check_{index}') == "1"
                    installation_data = {
                        'pd_name': data.get(f'pd_name_{index}'),
                        'capacity': data.get(f'capacity_{index}'),
                        'total_needed_capacity': data.get(f'total_needed_capacity_{index}'),
                        'waste_water_type': data.get(f'waste_water_type_{index}'),
                        'total_no_machines': data.get(f'total_no_machines_{index}'),
                        'is_checked': is_checked
                    }
                    Amc_Proposal.append(installation_data)

            for key in data.keys():
                if key.startswith("maintenance_support_check_"):
                    index = key.split("_")[-1]
                    is_checked = data.get(f"maintenance_support_check_{index}") == "1"
                    maintenance_support_value = data.get(f"maintenance_support_{index}")
                    if maintenance_support_value:
                        maintenance_support.append({"value": maintenance_support_value, "is_checked": is_checked})

            for key in data.keys():
                if key.startswith("yearly_maintenance_check_"):
                    index = key.split("_")[-1]
                    is_checked = data.get(f"yearly_maintenance_check_{index}") == "1"
                    yearly_maintenance_value = data.get(f"yearly_maintenance_{index}")
                    if yearly_maintenance_value:
                        yearly_maintenance.append({"value": yearly_maintenance_value, "is_checked": is_checked})

            for key in data.keys():
                if key.startswith("running_consumables_check_"):
                    index = key.split("_")[-1]
                    is_checked = data.get(f"running_consumables_check_{index}") == "1"
                    running_consumables_value = data.get(f"running_consumables_{index}")
                    if running_consumables_value:
                        running_consumables.append({"value": running_consumables_value, "is_checked": is_checked})

            for key in data.keys():
                if key.startswith("exclusions_check_"):
                    index = key.split("_")[-1]
                    is_checked = data.get(f"exclusions_check_{index}") == "1"
                    exclusions_value = data.get(f"exclusions_{index}")
                    if exclusions_value:
                        exclusions.append({"value": exclusions_value, "is_checked": is_checked})

            for key in data.keys():
                if key.startswith('select_amcp_check_'):
                    index = key.split('_')[-1]
                    is_checked = data.get(f'select_amcp_check_{index}') == "1"
                    installation_data = {
                        'pd_name': data.get(f'pd_namep_{index}'),
                        'capacity': data.get(f'capacityp_{index}'),
                        'total_needed_capacity': data.get(f'total_needed_capacityp_{index}'),
                        'waste_water_type': data.get(f'waste_water_typep_{index}'),
                        'total_no_machines': data.get(f'total_no_machinesp_{index}'),
                        'is_checked': is_checked
                    }
                    amc_pricing.append(installation_data)

            for key in data.keys():
                if key.startswith('select_per_check_'):
                    index = key.split('_')[-1]
                    is_checked = data.get(f'select_per_check_{index}') == "1"
                    installation_data = {
                        'particulars': data.get(f'particulars_{index}'),
                        'first_year_exgst': data.get(f'first_year_exgst_{index}'),
                        'is_checked': is_checked
                    }
                    Particulars.append(installation_data)
            for key in data.keys():
                if key.startswith("terms_check_"):
                    index = key.split("_")[-1]
                    is_checked = data.get(f"terms_check_{index}") == "1"
                    terms_value = data.get(f"terms_{index}")
                    if terms_value:
                        terms.append({"value": terms_value, "is_checked": is_checked})

            if "content_select_sub" in data:
                is_checked = data.get("content_select_sub") == "on"
                Subtotal_value = data.get("Subtotal1")
                if Subtotal_value:
                    Subtotal_list.append({"value": Subtotal_value, "is_checked": is_checked})

            if "content_select_gst" in data:
                is_checked = data.get("content_select_gst") == "on"
                gst_value = data.get("gst1")
                if gst_value:
                    GST.append({"value": gst_value, "is_checked": is_checked})

            if "content_select_gtotal" in data:
                is_checked = data.get("content_select_gtotal") == "on"
                gtotal_value = data.get("grand")
                if gtotal_value:
                    Grand_Total.append({"value": gtotal_value, "is_checked": is_checked})

            base_dir = os.path.join(settings.BASE_DIR, "stored_data", str(enquiry_id))
            os.makedirs(base_dir, exist_ok=True)
            existing_files = os.listdir(base_dir)
            # Robust versioning logic
            if "R" in quotation_number.split(".")[0][-3:]:
                # Split at the last occurrence of "R" and take the part before it
                base_name = quotation_number[:quotation_number.rfind("R")]
            else:
                base_name = quotation_number
            version_numbers = [
                int(f.split("R")[-1].split(".")[0])
                for f in existing_files
                if f.startswith(base_name) and f.endswith(".json") and "R" in f.split(".")[0][-3:]
            ]
            latest_version = max(version_numbers, default=0)
            new_version = latest_version + 1
            quotation = f"{base_name}R{new_version}"
            new_file_name = f"{quotation}.json"
            new_file_path = os.path.join(base_dir, new_file_name)

            final_data = {
                'contents': contents,
                'terms': terms,
                'Amc_Proposal': Amc_Proposal,
                'maintenance_support': maintenance_support,
                'yearly_maintenance': yearly_maintenance,
                'running_consumables': running_consumables,
                'exclusions': exclusions,
                'amc_pricing': amc_pricing,
                'Particulars': Particulars,
                'Subtotal_list': Subtotal_list,
                'GST': GST,
                'Grand_Total': Grand_Total,
                'enquiry_id': enquiry_id,
                'quotation_number': quotation,
            }
            with open(new_file_path, "w") as json_file:
                json.dump(final_data, json_file, indent=4)
            return JsonResponse({"message": "Quotation updated successfully", "file": new_file_name})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    data_json = json.dumps(quotation_data)
    return render(request, 'xp2/edit_quotation.html', {'quotation_data': quotation_data, 'data': data_json})


# def amc_edit(request,quotation_no):
#     company=companydetails.objects.all()
#     current_date = datetime.now().strftime('%d %b, %Y')

   

#     # Path to the stored_data directory
#     base_dir = settings.BASE_DIR
#     stored_data_dir = os.path.join(base_dir, 'stored_data')

#     # Traverse all directories in stored_data
#     found_data = None
#     for directory in os.listdir(stored_data_dir):
#         dir_path = os.path.join(stored_data_dir, directory)

#         if os.path.isdir(dir_path):  # Ensure it's a directory
#             # Look for a file matching the quotation_no
#             file_path = os.path.join(dir_path, f"{quotation_no}.json")

#             if os.path.exists(file_path):  # Check if the file exists
#                 # Load the JSON data
#                 with open(file_path, 'r') as file:
#                     try:
#                         found_data = json.load(file)
                    

#                     except json.JSONDecodeError:
#                         raise Http404(f"Invalid JSON file: {file_path}")
#                 break

#     # If no matching file is found, raise a 404
#     if not found_data:
#         raise Http404(f"Quotation with number {quotation_no} not found.")
    
#     return render(request, 'xp2/amc_edit.html', {
#         'quotation_no': quotation_no,
#         'data': found_data,
#         'current_date':current_date,
#         'company':company,
#     })
    
   


def proposal_get_quotation_number():
    # Define the file to store the last generated number
    storage_file = "quotation_number_store.json"

    # Get the current year and month in YYMM format
    current_year_month = datetime.now().strftime('%y%m')

    # Initialize the last recorded year and sequential number
    last_year_month = None
    last_sequential = 0

    # Check if the storage file exists
    if os.path.exists(storage_file):
        # Load the last record from the file
        with open(storage_file, "r") as file:
            data = json.load(file)
            last_year_month = data.get("last_year_month")
            last_sequential = data.get("last_sequential", 0)

    # If the current year and month differ, reset the sequential number
    if last_year_month != current_year_month:
        last_sequential = 0

    # Increment the sequential number for the current year and month
    next_sequential = last_sequential + 1

    # Format the sequential number as a 3-digit string with leading zeros
    sequential_part = str(next_sequential).zfill(3)

    # Generate the quotation number
    quotation_number = f"EL-HID-PR-{current_year_month}{sequential_part}"

    # Save the updated year-month and sequential number to the file AFTER generating the quotation number
    with open(storage_file, "w") as file:
        json.dump({
            "last_year_month": current_year_month,
            "last_sequential": next_sequential
        }, file)

    return quotation_number


from .models import SiteInfo,Table1,ReqSpecification,OutputTable,InstallationTable,SpecificationTable,OptionalHardwareTable,ContentsPR


def proposal_details(request, enquiry_id, product_id):
    try:
        # Fetch the enquiry based on the provided enquiry_id
        enquiry = Enquiry.objects.get(id=enquiry_id)
    except Enquiry.DoesNotExist:
        return render(request, 'xp2/error_page.html', {'error': 'Enquiry not found'})
    # Fetch all the required data
    products = QProduct.objects.all()
    site = SiteInfo.objects.all()
    table1 = Table1.objects.all()
    standard = StandardTable.objects.all()
    spec = SpecTable.objects.all()
    req = ReqSpecification.objects.all()
    output = OutputTable.objects.all()
    process = ProcessDescription.objects.all()
    inst = InstallationTable.objects.all()
    specifi = SpecificationTable.objects.all()
    hard = OptionalHardwareTable.objects.all()
    price = Pricing.objects.all()
    gterms = GeneralTermsAndConditions.objects.all()
    apendix = Appendix.objects.all()
    particulars = ParticularsTable.objects.all()

    # Filter the `Contents` table by pd_name matching the provided product_id
    contents = ContentsPR.objects.filter(pd_name=product_id)
    site = SiteInfo.objects.filter(pd_name=product_id)
    table1 = Table1.objects.filter(pd_name=product_id)
    standard = StandardTable.objects.filter(pd_name=product_id)
    spec = SpecTable.objects.filter(pd_name=product_id)
    req = ReqSpecification.objects.filter(pd_name=product_id)
    output = OutputTable.objects.filter(pd_name=product_id)
    process = ProcessDescription.objects.filter(pd_name=product_id)
    inst = InstallationTable.objects.filter(pd_name=product_id)
    specifi = SpecificationTable.objects.filter(pd_name=product_id)
    hard = OptionalHardwareTable.objects.filter(pd_name=product_id)
    products=QProduct.objects.filter(pd_name=product_id)
    price = Pricing.objects.filter(pd_name=product_id)
    gterms = GeneralTermsAndConditions.objects.filter(pd_name=product_id)
    apendix = Appendix.objects.filter(pd_name=product_id)
    particulars = ParticularsTable.objects.filter(pd_name=product_id)

    # Fetch the first Pricing object (or filter based on specific criteria)
    pricing = Pricing.objects.first()  # Adjust this query to match your requirements

    # Retrieve the terms_conditions field if the object exists
    terms = pricing.terms_conditions if pricing else ''

    # Split the terms into a list
    terms_and_conds = terms.split(".") if terms else []


    # Generate the quotation number
    quotation_number = proposal_get_quotation_number()

    # Prepare the context to pass to the template
    context = {
        'enquiry_id': enquiry_id,
        'products': products,
        'particulars': particulars,
        'contents': contents,
        'quotation_number': quotation_number,
        'site': site,
        'table1': table1,
        'standard': standard,
        'spec': spec,
        'req': req,
        'output': output,
        'process': process,
        'inst': inst,
        'specifi': specifi,
        'hard': hard,
        'price': price,
        'gterms': gterms,
        'apendix': apendix,
        'terms_and_conds':terms_and_conds,
    }

    # Render the template with the context
    return render(request, 'xp2/proposal_details.html', context)




def product_list(request, enquiry_id):
    try:
        enquiry = Enquiry.objects.get(id=enquiry_id)
    except Enquiry.DoesNotExist:
        return render(request, 'xp2/error_page.html', {'error': 'Enquiry not found'})

    # Fetch all products related to the enquiry
    products = QuotationProduct.objects.all()
    # Handle form submission
    if request.method == 'POST':
        selected_product_id = request.POST.get('selected_product')
        if selected_product_id:
            # Redirect to the amc_quotation_details view with the enquiry ID
            return redirect('amc_quotation_details', enquiry_id=enquiry_id,product_id=selected_product_id)

    return render(request, 'xp2/product_list.html', {'products': products, 'enquiry_id': enquiry_id})


from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import os, json, logging
from django.conf import settings

logger = logging.getLogger(__name__)

@csrf_exempt
def proposal_store_data(request, enquiry_id, quotation_number):
    logger.info("Received request: %s", request.method)
    if request.method != "POST":
        print("entered the loop")
        return JsonResponse(
            {"status": "error", "message": "Only POST requests are allowed"}, status=405
        )
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse(
            {"status": "error", "message": "This request is not an AJAX request"},
            status=400,
        )
    try:
        # Handle FormData (request.POST and request.FILES)
        data = request.POST.dict()
        print(data)
        print("entered the loop 2")
        quotation_number = data.get("quotation_number") or proposal_get_quotation_number()
        if not quotation_number:
            return JsonResponse(
                {"status": "error", "message": "Quotation number is missing"},
                status=400,
            )

        base_dir = os.path.join(settings.BASE_DIR, "proposal", str(enquiry_id))
        os.makedirs(base_dir, exist_ok=True)
        file_path = os.path.join(base_dir, f"{quotation_number}.json")

        base_dir1 = os.path.join(settings.BASE_DIR, "static", "process_diagrams", str(enquiry_id))
        os.makedirs(base_dir1, exist_ok=True)
        if os.path.exists(file_path):
            return JsonResponse(
                {"status": "error", "message": f"Quotation number {quotation_number} already exists for this enquiry"},
                status=400,
            )

        # Helper: only append if at least one key is non-empty and non-false
        def is_nonempty_row(d):
            return any((v if isinstance(v, bool) else (v and str(v).strip())) for v in d.values())

        # -- All Dynamic Lists initialized as before --
        contents, site_info, table_data, treatment_processes = [], [], [], []
        observations_and_suggestions, requirements_and_specifications = [], []
        specifications, process_diagram, process_description = [], [], []
        output_table, pricing, terms, installation = [], [], [], []
        specification, hardware, general_terms_conditions, appendix = [], [], [], []
        processed_indices, terms_indices, general_indices = set(), set(), set()
        processed_indices_supply_eq, processed_indices_dristi = set(), set()

        # ---- Preserve your logic, add is_nonempty_row filter to each list ----

        for key in data.keys():
            if key.startswith("content_select_"):
                index = key.split("_")[-1]
                content_select_value = data.get(f"content_select_{index}")
                is_checked = content_select_value in ["1", "on", "true"]  
                content_value = data.get(f"content_{index}")
                print(f"content", content_value)
                d = {"value": content_value, "is_checked": is_checked}
                if is_nonempty_row(d):
                    contents.append(d)

        for key in data.keys():
            if key.startswith('site_select_info_'):
                index = key.split('_')[-1]
                site_data = {
                    'is_checked': data.get(f'site_select_info_{index}') == "1",
                    'info_text': data.get(f'site_info_{index}'),
                    'is_standard_checked': data.get(f'site_select_standard_{index}') == "1",
                    'standard_text': data.get(f'site_standard_{index}')
                }
                if is_nonempty_row(site_data):
                    site_info.append(site_data)

        for key in data.keys():
            if key.startswith('sl_no_value_t1_'):
                index = key.split('_')[-1]
                table_row = {
                    'sl_no': data.get(f'sl_no_value_t1_{index}'),
                    'raw_sewage_characteristics': data.get(f'raw_sewage_characteristics_value_t1_{index}'),
                    'unit': data.get(f'unit_value_t1_{index}'),
                    'value': data.get(f'value_value_t1_{index}'),
                    'is_checked': data.get(f'select_row_t1_{index}') == "1"
                }
                if is_nonempty_row(table_row):
                    table_data.append(table_row)
        
        for key in data.keys():
            if key.startswith('standard_select_'):
                index = key.split('_')[-1]
                treatment_data = {
                    'is_checked': data.get(f'standard_select_{index}') == "1",
                    'principal_purpose_unit_process': data.get(f'principal_purpose_{index}'),
                    'unit_processes': data.get(f'unit_processes_{index}')
                }
                if is_nonempty_row(treatment_data):
                    treatment_processes.append(treatment_data)
        
        for key in data.keys():
            if key.startswith('observation_select_'):
                index = key.split('_')[-1]
                observation_data = {
                    'observation_checked': data.get(f'observation_select_{index}') == "1",
                    'observation': data.get(f'observation_{index}'),
                    'suggestion_checked': data.get(f'suggestion_select_{index}') == "1",
                    'suggestion': data.get(f'suggestion_{index}'),
                    'features_checked': data.get(f'features_select_{index}') == "1",
                    'features': data.get(f'features_{index}'),
                    'salient_checked': data.get(f'salient_select_{index}') == "1",
                    'salient': data.get(f'salient_{index}')
                }
                if is_nonempty_row(observation_data):
                    observations_and_suggestions.append(observation_data)
        
        for key in data.keys():
            if key.startswith('requirement_select_'):
                index = key.split('_')[-1]
                requirement_data = {
                    'requirement_checked': data.get(f'requirement_select_{index}') == "1",
                    'requirement_text': data.get(f'requirement_{index}', '')
                }
                if is_nonempty_row(requirement_data):
                    requirements_and_specifications.append(requirement_data)

        for key in data.keys():
            if key.startswith('spec_select_'):
                index = key.split('_')[-1]
                spec_data = {
                    'spec_checked': data.get(f'spec_select_{index}') == "1",
                    'specs_for_25kld': data.get(f'specs_for_25kld_{index}', ''),
                    'hidrec': data.get(f'hidrec_{index}', '')
                }
                if is_nonempty_row(spec_data):
                    specifications.append(spec_data)

        # Process diagrams – scan for diagram1_checked and diagram2_checked
                        # SAVE PROCESS DIAGRAMS INSIDE MEDIA FOLDER (CORRECT)
                media_process_dir = os.path.join(settings.MEDIA_ROOT, "process_diagrams", str(enquiry_id))
                os.makedirs(media_process_dir, exist_ok=True)

                for key in data.keys():
                    if key.startswith("process_diagram1_checked_") or key.startswith("process_diagram2_checked_"):
                        index = key.split("_")[-1]

                        process_diagram1_checked = data.get(f'process_diagram1_checked_{index}') == "1"
                        process_diagram2_checked = data.get(f'process_diagram2_checked_{index}') == "1"

                        process_diagram1_file = request.FILES.get(f'process_diagram1_url_{index}')
                        process_diagram2_file = request.FILES.get(f'process_diagram2_url_{index}')

                        process_diagram1_path = ""
                        process_diagram2_path = ""

                        if process_diagram1_checked and process_diagram1_file:
                            process_diagram1_path = os.path.join(
                                "process_diagrams",
                                str(enquiry_id),
                                f"process_diagram1_{index}_{process_diagram1_file.name}"
                            )
                            full_path = os.path.join(settings.MEDIA_ROOT, process_diagram1_path)
                            with open(full_path, "wb") as f:
                                for chunk in process_diagram1_file.chunks():
                                    f.write(chunk)

                        if process_diagram2_checked and process_diagram2_file:
                            process_diagram2_path = os.path.join(
                                "process_diagrams",
                                str(enquiry_id),
                                f"process_diagram2_{index}_{process_diagram2_file.name}"
                            )
                            full_path = os.path.join(settings.MEDIA_ROOT, process_diagram2_path)
                            with open(full_path, "wb") as f:
                                for chunk in process_diagram2_file.chunks():
                                    f.write(chunk)

                        diagram_data = {
                            'process_diagram1_checked': process_diagram1_checked,
                            'process_diagram1_path': process_diagram1_path,
                            'process_diagram2_checked': process_diagram2_checked,
                            'process_diagram2_path': process_diagram2_path,
                        }
                        process_diagram.append(diagram_data)

        for key in data.keys():
            if key.startswith("sl_no_value_op_"):
                index = key.split("_")[-1]
                is_selected = data.get(f"select_row_op_{index}") == "1"
                sl_no = data.get(f"sl_no_value_op_{index}", "").strip()
                treated_water_characteristics = data.get(f"treated_water_characteristics_value_op_{index}", "").strip()
                unit = data.get(f"unit_value_op_{index}", "").strip()
                standard_value = data.get(f"standard_value_op_{index}", "").strip()
                output_row = {
                    'sl_no': sl_no,
                    'treated_water_characteristics': treated_water_characteristics,
                    'unit': unit,
                    'standard_value': standard_value,
                    'is_checked': is_selected
                }
                if is_nonempty_row(output_row):
                    output_table.append({'output_data': output_row})

        for key in data.keys():
            if key.startswith("process_description_text_"):
                index = key.split("_")[-1]
                process_row = {
                    'process_description_checked': data.get(f"process_description_text_{index}") == "1",
                    'process_description': data.get(f"process_description_{index}"),
                    'is_checked': data.get(f'etp_text_{index}') == "1",
                    'etp_text': data.get(f'etp_text_value_{index}'),
                    'is_standard_checked': data.get(f'stp_text_{index}') == "1",
                    'stp_text': data.get(f'stp_text_value_{index}'),
                    'is_shs_checked': data.get(f'shs_text_{index}') == "1",
                    'shs_text': data.get(f'shs_text_value_{index}'),
                    'is_atm_checked': data.get(f'automation_text_{index}') == "1",
                    'automation_text': data.get(f'automation_text_value_{index}'),
                    'is_foot_checked': data.get(f'footprint_area_{index}') == "1",
                    'footprint_area': data.get(f'footprint_area_value_{index}'),
                    'is_tentative_checked': data.get(f'tentative_{index}') == "1",
                    'tentative_BOM': data.get(f'tentative__value_{index}'),
                }
                if is_nonempty_row(process_row):
                    process_description.append({'process_data': process_row})

        for key in data.keys():
            if key.startswith("machine_cost_text_"):
                index = key.split("_")[-1]
                pricing_row = {
                    'machine_cost_text': data.get(f"machine_cost_value_{index}"),
                    'is_machine_checked': data.get(f"machine_cost_text_{index}") == "1"
                }
                if is_nonempty_row(pricing_row):
                    pricing.append(pricing_row)

        for key in data.keys():
            if key.startswith("product_name_spe_"):
                index = key.split("_")[-1]
                installation_row = {
                    'product_name': data.get(f"product_name_spe_{index}", ""),
                    'capacity': data.get(f"capacity_value_spe_{index}", ""),
                    'total_needed_capacity': data.get(f"total_needed_capacity_value_spe_{index}", ""),
                    'waste_water_type': data.get(f"waste_water_type_value_spe_{index}", ""),
                    'total_no_machines': data.get(f"total_no_machines_value_spe_{index}", ""),
                    'is_checked': data.get(f"select_row_spe_{index}", "0") == "1"
                }
                if is_nonempty_row(installation_row):
                    installation.append(installation_row)

        for key in data.keys():
            if key.startswith("sl_no_value_det_"):
                index = key.split("_")[-1]
                specification_row = {
                    'sl_no': data.get(f"sl_no_value_det_{index}", ""),
                    'specification': data.get(f"specification_value_det_{index}", ""),
                    'qnty': data.get(f"qnty_value_det_{index}", ""),
                    'unit': data.get(f"unit_value_det_{index}", ""),
                    'unit_rate': data.get(f"unit_rate_value_det_{index}", ""),
                    'price_exgst': data.get(f"price_exgst_value_det_{index}", ""),
                    'total': data.get(f"total_value_det_{index}", ""),
                    'is_checked': data.get(f"select_row_det_{index}", "0") == "1"
                }
                if is_nonempty_row(specification_row):
                    specification.append(specification_row)

        for key in data.keys():
            if key.startswith("sl_no_value_opt_"):
                index = key.split("_")[-1]
                hardware_row = {
                    'sl_no': data.get(f"sl_no_value_opt_{index}", ""),
                    'optional_hardware': data.get(f"optional_hardware_value_opt_{index}", ""),
                    'qnty': data.get(f"qnty_value_opt_{index}", ""),
                    'unit': data.get(f"unit_value_opt_{index}", ""),
                    'unit_rate': data.get(f"unit_rate_value_opt_{index}", ""),
                    'price_exgst': data.get(f"price_exgst_value_opt_{index}", ""),
                    'total': data.get(f"total_value_opt_{index}", ""),
                    'is_checked': data.get(f"select_row_opt_{index}", "0") == "1"
                }
                if is_nonempty_row(hardware_row):
                    hardware.append(hardware_row)

        for key in request.POST.keys():
            if key.startswith("terms_") and not key.startswith("terms_check_"):
                index = key.split("_")[1]
                term_text = request.POST.get(f"terms_{index}")
                is_checked = request.POST.get(f"terms_check_{index}") == "1"
                term_row = {"text": term_text, "is_checked": is_checked}
                if is_nonempty_row(term_row):
                    terms.append(term_row)

        for key in data.keys():
            if key.startswith('performance_'):
                index = key.split('_')[-1]
                if index in general_indices:
                    continue
                term_data = {
                    'performance_checked': data.get(f'performance_{index}') == "1",
                    'performance_text': data.get(f'performance_text_{index}'),
                    'flow_characteristics_checked': data.get(f'flow_characteristics_{index}') == "1",
                    'flow_characteristics_text': data.get(f'flow_characteristics_text_{index}'),
                    'trial_quality_check_checked': data.get(f'trial_quality_check_{index}') == "1",
                    'trial_quality_check_text': data.get(f'trial_quality_check_text_{index}'),
                    'virtual_completion_checked': data.get(f'virtual_completion_{index}') == "1",
                    'virtual_completion_text': data.get(f'virtual_completion_text_{index}'),
                    'limitation_liability_checked': data.get(f'limitation_liability_{index}') == "1",
                    'limitation_liability_text': data.get(f'limitation_liability_text_{index}'),
                    'force_clause_checked': data.get(f'force_clause_{index}') == "1",
                    'force_clause_text': data.get(f'force_clause_text_{index}'),
                    'additional_works_checked': data.get(f'additional_works_{index}') == "1",
                    'additional_works_text': data.get(f'additional_works_text_{index}'),
                    'warranty_guaranty_checked': data.get(f'warranty_guaranty_{index}') == "1",
                    'warranty_guaranty_text': data.get(f'warranty_guaranty_text_{index}'),
                    'arbitration_checked': data.get(f'arbitration_{index}') == "1",
                    'arbitration_text': data.get(f'arbitration_text_{index}'),
                    'validity_checked': data.get(f'validity_{index}') == "1",
                    'validity_text': data.get(f'validity_text_{index}')
                }
                if is_nonempty_row(term_data):
                    if term_data not in general_terms_conditions:
                        general_terms_conditions.append(term_data)
                general_indices.add(index)

            for key in data.keys():
                if key.startswith('supply_eq_'):
                    index = key.split('_')[-1]
                    if index in processed_indices_supply_eq:
                        continue
                    appendix_data = {
                        'supply_eq_checked': data.get(f'supply_eq_{index}') == "1",
                        'supply_eq_text': data.get(f'supply_eq_text_{index}'),
                        'instal_commissioning_checked': data.get(f'instal_commissioning_{index}') == "1",
                        'instal_commissioning_text': data.get(f'instal_commissioning_text_{index}'),
                        'clients_scope_checked': data.get(f'clients_scope_{index}') == "1",
                        'clients_scope_text': data.get(f'clients_scope_text_{index}'),
                        'note_checked': data.get(f'note_{index}') == "1",
                        'note_text': data.get(f'note_text_{index}'),
                        'dristi_checked': data.get(f'dristi_{index}') == "1",
                        'dristi_subscription_text': data.get(f'dristi_subscription_{index}'),
                        'iot_checked': data.get(f'iot_{index}') == "1",
                        'iot_hardware_text': data.get(f'iot_hardware_{index}'),
                        'dristi_checked': data.get(f'dristi_{index}') == "1",
                        'dristi_subscription_text': data.get(f'dristi_subscription_{index}'),
                        'iot_checked': data.get(f'iot_{index}') == "1",
                        'iot_hardware_text': data.get(f'iot_hardware_{index}'),
                    }
                    if is_nonempty_row(appendix_data):
                        if appendix_data not in appendix:
                            appendix.append(appendix_data)
                    processed_indices_supply_eq.add(index)

        final_data = {
            'quotation_number': quotation_number,
            'contents': contents,
            'site_info': site_info,
            'table_data': table_data,
            'treatment_processes': treatment_processes,
            'observations_and_suggestions': observations_and_suggestions,
            'requirements_and_specifications': requirements_and_specifications,
            'specifications': specifications,
            'process_diagram': process_diagram,
            'process_description': process_description,
            'output_table': output_table,
            'pricing': pricing,
            'installation': installation,
            'specification': specification,
            'hardware': hardware,
            'general_terms_conditions': general_terms_conditions,
            'appendix': appendix,
            'enquiry_id': enquiry_id,
            'terms': terms,
        }

        with open(file_path, "w") as json_file:
            json.dump(final_data, json_file, indent=4)
        logger.info("Data stored successfully at: %s", file_path)
        for key, value in final_data.items():
            print(f"{key}: {value}")
        return JsonResponse(
            {"status": "success", "message": "Data stored successfully", "file_path": file_path}
        )

    except Exception as e:
        logger.error("An unexpected error occurred", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)




import os
import json
from datetime import datetime
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from .models import companydetails  # Adjust as needed

def proposal_preview(request, quotation_no):
    company = companydetails.objects.all()
    current_date = datetime.now().strftime('%d %b, %Y')

    # Directories to check
    data_dirs = [
        os.path.join(settings.BASE_DIR, 'proposal'),
        os.path.join(settings.BASE_DIR, 'proposal_draft'),
    ]
    found_data = None

    for base_dir in data_dirs:
        if not os.path.exists(base_dir):
            continue
        for directory in os.listdir(base_dir):
            dir_path = os.path.join(base_dir, directory)
            if not os.path.isdir(dir_path):
                continue
            file_path = os.path.join(dir_path, f"{quotation_no}.json")
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        found_data = json.load(file)
                    break
                except json.JSONDecodeError:
                    raise Http404(f"Invalid JSON file: {file_path}")
        if found_data:
            break

    if not found_data:
        raise Http404(f"Quotation with number {quotation_no} not found.")

    data = found_data

    # Helper for appendix subsections
    def appendix_has(section_key):
        return any(a.get(section_key) for a in data.get('appendix', []))

    # Section flags
    has_contents = bool(data.get('contents'))
    has_site_info = any(i.get('is_checked') or i.get('is_standard_checked') for i in data.get('site_info', []))
    has_raw_sewage = any(t.get('is_checked') for t in data.get('table_data', []))
    has_treatment = any(t.get('is_checked') for t in data.get('treatment_processes', []))
    has_obs_sugg = any(
        o.get('observation_checked') or o.get('suggestion_checked') or o.get('features') or o.get('salient')
        for o in data.get('observations_and_suggestions', [])
    )
    has_requirements = any(r.get('requirement_checked') for r in data.get('requirements_and_specifications', []))
    has_specs = any(s.get('spec_checked') for s in data.get('specifications', []))
    has_process_diagram = any(d.get('process_diagram_checked') for d in data.get('process_diagram', []))

    has_process_desc = any(
        d.get('process_data', {}).get('process_description_checked')
        for d in data.get('process_description', [])
    )
    has_output = any(
        o.get('output_data', {}).get('is_checked')
        for o in data.get('output_table', [])
    )
    has_pricing = any(p.get('is_checked') for p in data.get('pricing', []))
    has_installation = any(i.get('is_checked') for i in data.get('installation', []))
    has_specification = any(s.get('is_checked') for s in data.get('specification', []))
    has_terms = any(t.get('is_checked') for t in data.get('terms', []))
    # General terms: only show if there's any checked field
    has_general_terms = any(
        g and any(
            g.get(f"{field}_checked")
            for field in [
                "performance", "flow_characteristics", "trial_quality_check", "virtual_completion",
                "limitation_liability", "force_clause", "additional_works", "warranty_guaranty", "arbitration", "validity"
            ]
        )
        for g in data.get("general_terms_conditions", [])
    )
    # Appendix: show only if any content
    has_appendix = any(
        a and any(
            a.get(k)
            for k in [
                "supply_eq_checked", "instal_commissioning_checked", "clients_scope_checked",
                "note_checked", "dristi_checked", "iot_checked"
            ]
        )
        for a in data.get('appendix', [])
    )
    # Appendix table (installation)
    has_appendix_table = any(i.get("is_checked") for i in data.get('installation', []))
    # Individual inclusions
    has_supply_eq = appendix_has('supply_eq_checked')
    has_instal_commissioning = appendix_has('instal_commissioning_checked')
    has_clients_scope = appendix_has('clients_scope_checked')
    has_note = appendix_has('note_checked')
    has_dristi = appendix_has('dristi_checked')
    has_iot = appendix_has('iot_checked')

    # Pass all flags to the template
    return render(request, 'xp2/proposal_preview.html', {
        'quotation_no': quotation_no,
        'data': found_data,
        'current_date': current_date,
        'company': company,

        # Section flags for headers
        'has_contents': has_contents,
        'has_site_info': has_site_info,
        'has_raw_sewage': has_raw_sewage,
        'has_treatment': has_treatment,
        'has_obs_sugg': has_obs_sugg,
        'has_requirements': has_requirements,
        'has_specs': has_specs,
        'has_process_diagram': has_process_diagram,
        'has_process_desc': has_process_desc,
        'has_output': has_output,
        'has_pricing': has_pricing,
        'has_installation': has_installation,
        'has_specification': has_specification,
        'has_terms': has_terms,
        'has_general_terms': has_general_terms,
        'has_appendix': has_appendix,
        'has_appendix_table': has_appendix_table,
        # Appendix inclusion flags
        'has_supply_eq': has_supply_eq,
        'has_instal_commissioning': has_instal_commissioning,
        'has_clients_scope': has_clients_scope,
        'has_note': has_note,
        'has_dristi': has_dristi,
        'has_iot': has_iot,
    })


def product_pr(request, enquiry_id):
    try:
        enquiry = Enquiry.objects.get(id=enquiry_id)
    except Enquiry.DoesNotExist:
        return render(request, 'xp2/error_page.html', {'error': 'Enquiry not found'})

    # Fetch all products related to the enquiry
    products = QuotationProduct.objects.all()
    # Handle form submission
    if request.method == 'POST':
        selected_product_id = request.POST.get('selected_product')
        if selected_product_id:
            # Redirect to the amc_quotation_details view with the enquiry ID
            return redirect('proposal_details', enquiry_id=enquiry_id,product_id=selected_product_id)

    return render(request, 'xp2/product_list_pr.html', {'products': products, 'enquiry_id': enquiry_id})



from django.shortcuts import get_object_or_404, redirect, render
from .models import confirmed_enquiry,RevertRemark

from django.shortcuts import get_object_or_404, redirect
from django.utils.timezone import now
from django.contrib import messages

def revert_to_enquiries(request, enquiry_id):
    if request.method == "POST":
        # Get the remarks and timestamp from the form
        remarks = request.POST.get("remarks")
        timestamp = request.POST.get("timestamp") or now()  # Default to current timestamp

        # Get the enquiry object
        enquiry = get_object_or_404(Enquiry, id=enquiry_id, is_confirmed=True)

        # Create a new revert remark and save it
        RevertRemark.objects.create(
            enquiry=enquiry,
            text=remarks,
            created_at=timestamp
        )

        # Update the enquiry's status
        enquiry.is_reverted = True  # Mark as reverted
        enquiry.save()

        # Update the `revert` status for all related `confirmed_enquiry` entries
        confirmed_enquiries = confirmed_enquiry.objects.filter(enquiry=enquiry)
        confirmed_enquiries.update(revert=True)  # Update all related entries in bulk

        # Redirect to the desired page with a success message
        messages.success(request, "Enquiry successfully reverted.")
        return redirect('enquries')  # Make sure 'enquiries' is the correct URL name

    # Redirect for non-POST requests
    return redirect('enquries')



def edit_quotation_pr(request, enquiry_id, quotation_number):
    logger.info("Editing Quotation: %s, %s", enquiry_id, quotation_number)

    # Define the file path for the existing quotation data (JSON file)
    file_path = os.path.join(settings.BASE_DIR, "proposal", str(enquiry_id), f"{quotation_number}.json")
    print(f"path:",file_path)
    # Check if the file exists
    if not os.path.exists(file_path):
        return JsonResponse({"status": "error", "message": "Quotation not found"}, status=404)
    

    base_dir1 = os.path.join(settings.BASE_DIR, "process_diagrams", str(enquiry_id))
    os.makedirs(base_dir1, exist_ok=True)
    # Load the existing quotation data from the file
    with open(file_path, "r") as json_file:
        proposal_data = json.load(json_file)
    if request.method == "POST":
        data = request.POST
        print("post received")
        contents = []
        site_info=[]
        table_data = []
        treatment_processes = []
        observations_and_suggestions = []
        requirements_and_specifications = []
        specifications = []
        process_diagram = []
        process_description = []
        output_table = []
        pricing = []
        terms = []
        installation = []
        specification = []
        hardware = []
        general_terms_conditions = []
        appendix = []
        processed_indices = set()
        terms_indices=set()
        general_indices=set()
        processed_indices_supply_eq = set()  
        processed_indices_dristi = set() 
        try:
            print("post received 2")
            for key in data.keys():
                print("post received 3")
                if key.startswith("content_select_"):
                    index = key.split("_")[-1]
                    content_select_value = data.get(f"content_select_{index}")
                    is_checked = content_select_value in ["1", "on", "true"]  
                    content_value = data.get(f"content_{index}")
                    print(f"content",content_value)
                    if content_value:
                        contents.append({"value": content_value, "is_checked": is_checked})

            for key in data.keys():
                if key.startswith('site_select_info_'):
                    index = key.split('_')[-1]
                    site_data = {
                        'is_checked': data.get(f'site_select_info_{index}') == "1",
                        'info_text': data.get(f'site_info_{index}'),
                        'is_standard_checked': data.get(f'site_select_standard_{index}') == "1",
                        'standard_text': data.get(f'site_standard_{index}')
                    }
                    site_info.append(site_data)
            for key in data.keys():
                if key.startswith('sl_no_value_t1_'):
                    # Extract the index of the current row from the key
                    index = key.split('_')[-1]
                    
                    # Construct the row dictionary
                    table_row = {
                        'sl_no': data.get(f'sl_no_value_t1_{index}'),
                        'raw_sewage_characteristics': data.get(f'raw_sewage_characteristics_value_t1_{index}'),
                        'unit': data.get(f'unit_value_t1_{index}'),
                        'value': data.get(f'value_value_t1_{index}'),
                        # Checkbox state: True if checked, False otherwise
                        'is_checked': data.get(f'select_row_t1_{index}') == "1"  # Check if the checkbox was checked
                    }
                    # Append the row to the table data list
                    table_data.append(table_row)
            for key in data.keys():
                if key.startswith('standard_select_'):
                    # Extract the index of the current row from the key
                    index = key.split('_')[-1]
                    
                    # Construct the treatment process dictionary
                    treatment_data = {
                        'is_checked': data.get(f'standard_select_{index}') == "1",  # Checkbox checked state
                        'principal_purpose_unit_process': data.get(f'principal_purpose_{index}'),  # Principal purpose
                        'unit_processes': data.get(f'unit_processes_{index}')  # Unit processes
                    }
                    
                    # Append the treatment process data to the list
                    treatment_processes.append(treatment_data)
            for key in data.keys():
                if key.startswith('observation_select_'):
                    index = key.split('_')[-1]
                    observation_data = {
                        'observation_checked': data.get(f'observation_select_{index}') == "1",
                        'observation': data.get(f'observation_{index}'),
                        'suggestion_checked': data.get(f'suggestion_select_{index}') == "1",
                        'suggestion': data.get(f'suggestion_{index}'),
                        'features_checked': data.get(f'features_select_{index}') == "1",
                        'features': data.get(f'features_{index}'),
                        'salient_checked': data.get(f'salient_select_{index}') == "1",
                        'salient': data.get(f'salient_{index}')
                    }
                    observations_and_suggestions.append(observation_data)
            # site_info.append({'observations_and_suggestions': observations_and_suggestions})
            for key in data.keys():
                if key.startswith('requirement_select_'):
                    index = key.split('_')[-1]    
                    requirement_data = {
                        'requirement_checked': data.get(f'requirement_select_{index}') == "1",
                        'requirement_text': data.get(f'requirement_{index}', '')
                    }
                    requirements_and_specifications.append(requirement_data)

            # requirements_and_specifications.append({'requirements_and_specifications': requirements_and_specifications})
            for key in data.keys():
                if key.startswith('spec_select_'):
                    # Extract the index from the key
                    index = key.split('_')[-1]
                    
                    # Construct the spec data dictionary
                    spec_data = {
                        'spec_checked': data.get(f'spec_select_{index}') == "1",  # Checkbox checked state
                        'specs_for_25kld': data.get(f'specs_for_25kld_{index}', ''),  # Specs for 25 KLD
                        'hidrec': data.get(f'hidrec_{index}', '')  # HIDREC value
                    }
                    
                    # Append the spec data to the specifications list
                    specifications.append(spec_data)
            for key in data.keys():
                if key.startswith('process_diagram_'):
                    # Extract the index from the key name
                    index = key.split('_')[-1]

                    process_diagram_checked = data.get(f'process_diagram_{index}') == "1"
                    req_text = data.get(f'req_text_{index}', '')

                    # Retrieve checkbox values to check if the images are selected
                    process_diagram1_checked = data.get(f'process_diagram1_checked_{index}') == "1"
                    process_diagram2_checked = data.get(f'process_diagram2_checked_{index}') == "1"

                    # Retrieve uploaded files
                    process_diagram1_file = request.FILES.get(f'process_diagram1_url_{index}', None)
                    process_diagram2_file = request.FILES.get(f'process_diagram2_url_{index}', None)

                    # Initialize variables for file paths
                    process_diagram1_path = ''
                    process_diagram2_path = ''

                    # Save the file paths if checked
                    if process_diagram1_checked and process_diagram1_file:
                        # Define the relative path for the process diagram 1 file
                        process_diagram1_path = os.path.join("static", "process_diagrams", str(enquiry_id), f"process_diagram1_{index}_{process_diagram1_file.name}")
                        process_diagram1_path = process_diagram1_path.replace("\\", "/")  # Normalize to forward slashes

                        # Save the file to the specified path inside static
                        with open(os.path.join(settings.BASE_DIR, process_diagram1_path), 'wb') as f:
                            for chunk in process_diagram1_file.chunks():
                                f.write(chunk)

                    if process_diagram2_checked and process_diagram2_file:
                        # Define the relative path for the process diagram 2 file
                        process_diagram2_path = os.path.join("static", "process_diagrams", str(enquiry_id), f"process_diagram2_{index}_{process_diagram2_file.name}")
                        process_diagram2_path = process_diagram2_path.replace("\\", "/")  # Normalize to forward slashes

                        # Save the file to the specified path inside static
                        with open(os.path.join(settings.BASE_DIR, process_diagram2_path), 'wb') as f:
                            for chunk in process_diagram2_file.chunks():
                                f.write(chunk)

                    # Gather the diagram data, including the file paths and checkbox statuses
                    diagram_data = {
                        'process_diagram1_checked': process_diagram1_checked,
                        'process_diagram1_path': process_diagram1_path.replace("static/", ""),  # Remove 'static/' for cleaner paths
                        'process_diagram2_checked': process_diagram2_checked,
                        'process_diagram2_path': process_diagram2_path.replace("static/", ""),  # Remove 'static/' for cleaner paths
                        'process_diagram_checked': process_diagram_checked,
                        'req_text': req_text,
                    }

                    # Append the diagram data to the list
                    process_diagram.append(diagram_data)
            for key in data.keys():
                if key.startswith("sl_no_value_op_"):
                    index = key.split("_")[-1]
                    
                    # Check if the row is selected
                    is_selected = data.get(f"select_row_op_{index}") == "1"
                    
                    # Retrieve other values
                    sl_no = data.get(f"sl_no_value_op_{index}", "").strip()
                    treated_water_characteristics = data.get(f"treated_water_characteristics_value_op_{index}", "").strip()
                    unit = data.get(f"unit_value_op_{index}", "").strip()
                    standard_value = data.get(f"standard_value_op_{index}", "").strip()
                    
                    # Only add rows with valid data or if explicitly selected
                    if sl_no or treated_water_characteristics or unit or standard_value or is_selected:
                        output_row = {
                            'sl_no': sl_no,
                            'treated_water_characteristics': treated_water_characteristics,
                            'unit': unit,
                            'standard_value': standard_value,
                            'is_checked': is_selected
                        }
                        output_table.append({'output_data': output_row})
            for key in data.keys():
                if key.startswith("process_description_text_"):
                    index = key.split("_")[-1]
                    process_row = {

                        'process_description_checked': data.get(f"process_description_text_{index}") == "1",
                        'process_description': data.get(f"process_description_{index}"),

                        'is_checked': data.get(f'etp_text_{index}') == "1",
                        'etp_text': data.get(f'etp_text_value_{index}'),

                        'is_standard_checked': data.get(f'stp_text_{index}') == "1",
                        'stp_text': data.get(f'stp_text_value_{index}'),

                        'is_shs_checked': data.get(f'shs_text_{index}') == "1",
                        'shs_text': data.get(f'shs_text_value_{index}'),

                        'is_atm_checked': data.get(f'automation_text_{index}') == "1",
                        'automation_text': data.get(f'automation_text_value_{index}'),

                        'is_foot_checked': data.get(f'footprint_area_{index}') == "1",
                        'footprint_area': data.get(f'footprint_area_value_{index}'),

                        'is_tentative_checked': data.get(f'tentative_{index}') == "1",
                        'tentative_BOM': data.get(f'tentative__value_{index}'),
                    }
                    process_description.append({'process_data': process_row})
            for key in data.keys():
                if key.startswith("machine_cost_text_"):
                    index = key.split("_")[-1]
                    pricing_row = {
                        'machine_cost_text': data.get(f"machine_cost_value_{index}"),
                        'is_machine_checked': data.get(f"machine_cost_text_{index}") == "1"
                    }
                    pricing.append(pricing_row)

            for key in data.keys():
                if key.startswith("product_name_spe_"):
                    index = key.split("_")[-1]
                    installation_row = {
                        'product_name': data.get(f"product_name_spe_{index}", ""),
                        'capacity': data.get(f"capacity_value_spe_{index}", ""),
                        'total_needed_capacity': data.get(f"total_needed_capacity_value_spe_{index}", ""),
                        'waste_water_type': data.get(f"waste_water_type_value_spe_{index}", ""),
                        'total_no_machines': data.get(f"total_no_machines_value_spe_{index}", ""),
                        'is_checked': data.get(f"select_row_spe_{index}", "0") == "1"  # Checks if the checkbox is selected
                    }
                    installation.append(installation_row)

            for key in data.keys():
                if key.startswith("sl_no_value_det_"):
                    index = key.split("_")[-1]
                    specification_row = {
                        'sl_no': data.get(f"sl_no_value_det_{index}", ""),
                        'specification': data.get(f"specification_value_det_{index}", ""),
                        'qnty': data.get(f"qnty_value_det_{index}", ""),
                        'unit': data.get(f"unit_value_det_{index}", ""),
                        'unit_rate': data.get(f"unit_rate_value_det_{index}", ""),
                        'price_exgst': data.get(f"price_exgst_value_det_{index}", ""),
                        'total': data.get(f"total_value_det_{index}", ""),
                        'is_checked': data.get(f"select_row_det_{index}", "0") == "1"  # Checkbox value handling
                    }
                    specification.append(specification_row)

            for key in data.keys():
                if key.startswith("sl_no_value_opt_"):
                    index = key.split("_")[-1]
                    hardware_row = {
                        'sl_no': data.get(f"sl_no_value_opt_{index}", ""),
                        'optional_hardware': data.get(f"optional_hardware_value_opt_{index}", ""),
                        'qnty': data.get(f"qnty_value_opt_{index}", ""),
                        'unit': data.get(f"unit_value_opt_{index}", ""),
                        'unit_rate': data.get(f"unit_rate_value_opt_{index}", ""),
                        'price_exgst': data.get(f"price_exgst_value_opt_{index}", ""),
                        'total': data.get(f"total_value_opt_{index}", ""),
                        'is_checked': data.get(f"select_row_opt_{index}", "0") == "1"  # Handle checkbox state
                    }
                    hardware.append(hardware_row)

            for key in request.POST.keys():
                if key.startswith("terms_") and not key.startswith("terms_check_"):
                    # Get the index from the key (e.g., "terms_1" -> "1")
                    index = key.split("_")[1]

                    # Retrieve the term text and checkbox status
                    term_text = request.POST.get(f"terms_{index}")
                    is_checked = request.POST.get(f"terms_check_{index}") == "1"

                    # Append the term as a dictionary
                    terms.append({
                        "text": term_text,
                        "is_checked": is_checked
                    })

            for key in data.keys():
                if key.startswith('performance_'):
                    index = key.split('_')[-1]

                    # Skip if this index has already been processed
                    if index in general_indices:
                        continue

                    term_data = {
                        'performance_checked': data.get(f'performance_{index}') == "1",
                        'performance_text': data.get(f'performance_text_{index}'),

                        'flow_characteristics_checked': data.get(f'flow_characteristics_{index}') == "1",
                        'flow_characteristics_text': data.get(f'flow_characteristics_text_{index}'),

                        'trial_quality_check_checked': data.get(f'trial_quality_check_{index}') == "1",
                        'trial_quality_check_text': data.get(f'trial_quality_check_text_{index}'),

                        'virtual_completion_checked': data.get(f'virtual_completion_{index}') == "1",
                        'virtual_completion_text': data.get(f'virtual_completion_text_{index}'),

                        'limitation_liability_checked': data.get(f'limitation_liability_{index}') == "1",
                        'limitation_liability_text': data.get(f'limitation_liability_text_{index}'),

                        'force_clause_checked': data.get(f'force_clause_{index}') == "1",
                        'force_clause_text': data.get(f'force_clause_text_{index}'),

                        'additional_works_checked': data.get(f'additional_works_{index}') == "1",
                        'additional_works_text': data.get(f'additional_works_text_{index}'),

                        'warranty_guaranty_checked': data.get(f'warranty_guaranty_{index}') == "1",
                        'warranty_guaranty_text': data.get(f'warranty_guaranty_text_{index}'),

                        'arbitration_checked': data.get(f'arbitration_{index}') == "1",
                        'arbitration_text': data.get(f'arbitration_text_{index}'),

                        'validity_checked': data.get(f'validity_{index}') == "1",
                        'validity_text': data.get(f'validity_text_{index}')
                    }

                    # Add to the list only if it's not already present
                    if term_data not in general_terms_conditions:
                        general_terms_conditions.append(term_data)

                    # Mark this index as processed
                    general_indices.add(index)
            for key in data.keys():
                if key.startswith('supply_eq_'):
                    index = key.split('_')[-1]
                    
                    if index in processed_indices_supply_eq:
                        continue

                    appendix_data = {
                        'supply_eq_checked': data.get(f'supply_eq_{index}') == "1",
                        'supply_eq_text': data.get(f'supply_eq_text_{index}'),
                        
                        'instal_commissioning_checked': data.get(f'instal_commissioning_{index}') == "1",
                        'instal_commissioning_text': data.get(f'instal_commissioning_text_{index}'),
                        
                        'clients_scope_checked': data.get(f'clients_scope_{index}') == "1",
                        'clients_scope_text': data.get(f'clients_scope_text_{index}'),
                        
                        'note_checked': data.get(f'note_{index}') == "1",
                        'note_text': data.get(f'note_text_{index}'),

                        'dristi_checked': data.get(f'dristi_{index}') == "1",
                        'dristi_subscription_text': data.get(f'dristi_subscription_{index}'),
                        
                        'iot_checked': data.get(f'iot_{index}') == "1",
                        'iot_hardware_text': data.get(f'iot_hardware_{index}'),

                        'dristi_checked': data.get(f'dristi_{index}') == "1",
                        'dristi_subscription_text': data.get(f'dristi_subscription_{index}'),
                        
                        'iot_checked': data.get(f'iot_{index}') == "1",
                        'iot_hardware_text': data.get(f'iot_hardware_{index}'),
                    }

                    if appendix_data not in appendix:
                        appendix.append(appendix_data)

                    processed_indices_supply_eq.add(index)


            base_dir = os.path.join(settings.BASE_DIR, "proposal", str(enquiry_id))
            print("post received 4")
            os.makedirs(base_dir, exist_ok=True)
            existing_files = os.listdir(base_dir)
            if "R" in quotation_number.split(".")[0][-3:]:
                # Split at the last occurrence of "R" and take the part before it
                base_name = quotation_number[:quotation_number.rfind("R")]
            else:
                base_name = quotation_number

            # Extract version numbers for files matching the base name
            version_numbers = [
                int(f.split("R")[-1].split(".")[0])  # Extract the version number
                for f in existing_files
                if f.startswith(base_name) and f.endswith(".json") and "R" in f.split(".")[0][-3:]
            ]

            # Calculate the next version
            latest_version = max(version_numbers, default=0)
            new_version = latest_version + 1
            quotation = f"{base_name}R{new_version}"
            # Construct the new file name
            new_file_name = f"{quotation}.json"
            new_file_path = os.path.join(base_dir, new_file_name)
            print(f"Base name: {base_name}")
            print(f"Existing versions: {version_numbers}")
            print(f"New file name: {new_file_name}")
            print(f"New file path: {new_file_path}")
            # Save the edited data to the new versioned file
            final_data = {
                    'quotation_number': quotation,
                    'contents': contents,
                    'site_info': site_info,
                    'table_data': table_data,
                    'treatment_processes': treatment_processes,
                    'observations_and_suggestions': observations_and_suggestions,
                    'requirements_and_specifications': requirements_and_specifications,
                    'specifications': specifications,
                    'process_diagram': process_diagram,
                    'process_description': process_description,
                    'output_table': output_table,
                    'pricing': pricing,
                    'installation': installation,
                    'specification':specification,
                    'hardware':hardware,
                    'general_terms_conditions':general_terms_conditions,
                    'appendix':appendix,
                    'enquiry_id': enquiry_id,
                    'terms':terms,
                }
            edited_data = final_data
            print(f"edited",edited_data)
            with open(new_file_path, "w") as json_file:
                json.dump(edited_data, json_file, indent=4)
            return JsonResponse({"message": "Quotation updated successfully", "file": new_file_name})    
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)    
    print(proposal_data)
    # Return the template with the existing data for editing
    data_json = json.dumps(proposal_data)
    return render(request, 'xp2/proposal_edit.html', {'proposal_data': proposal_data, 'data': data_json})



def draft_store_data(request, enquiry_id, quotation_number):
    logger.info("Received request: %s", request.method)

    if request.method != "POST":
        return JsonResponse(
            {"status": "error", "message": "Only POST requests are allowed"}, status=405
        )


    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse(
            {"status": "error", "message": "This request is not an AJAX request"},
            status=400,
        )

    try:
        # Handle FormData (request.POST and request.FILES)
        data = request.POST.dict()

        quotation_number = data.get("quotation_number")
        if not quotation_number:
            return JsonResponse(
                {"status": "error", "message": "Quotation number is missing"},
                status=400,
            )
        # Define base directory for the enquiry_id
        base_dir = os.path.join(settings.BASE_DIR, "AMC_draft", str(enquiry_id))
        os.makedirs(base_dir, exist_ok=True)
        file_path = os.path.join(base_dir, f"{quotation_number}.json")

        # Check if file already exists
        if os.path.exists(file_path):
            return JsonResponse(
                {"status": "error", "message": f"Quotation number {quotation_number} already exists for this enquiry"},
                status=400,
            )

        # Initialize lists to hold form data
        contents = []
        maintenance_support = []
        yearly_maintenance = []
        running_consumables = []
        Amc_Proposal = []
        exclusions = []
        amc_pricing = []
        Particulars = []
        Subtotal_list = []
        GST = []
        Grand_Total = []
        terms = []

        # Process each section of the form that has a checkbox
        # Contents Section
        for key in data.keys():
            if key.startswith("content_select_"):
                index = key.split("_")[-1]
                content_select_value = data.get(f"content_select_{index}")
                is_checked = content_select_value in ["1", "on", "true"]  # Adjust this comparison based on the actual values received
                content_value = data.get(f"content_{index}")
                if content_value:
                    contents.append({"value": content_value, "is_checked": is_checked})

        # Amc_Proposal (Installations) Section
        for key in data.keys():
            if key.startswith('select_amc_check_'):

                index = key.split('_')[-1]
                is_checked = data.get(f'select_amc_check_{index}') == "1"
                installation_data = {
                    'pd_name': data.get(f'pd_name_{index}'),
                    'capacity': data.get(f'capacity_{index}'),
                    'total_needed_capacity': data.get(f'total_needed_capacity_{index}'),
                    'waste_water_type': data.get(f'waste_water_type_{index}'),
                    'total_no_machines': data.get(f'total_no_machines_{index}'),
                    'is_checked': is_checked
                }
                Amc_Proposal.append(installation_data)
        # Inclusions Section
        for key in data.keys():
            if key.startswith("maintenance_support_check_"):
                index = key.split("_")[-1]
                is_checked = data.get(f"maintenance_support_check_{index}") == "1"
                maintenance_support_value = data.get(f"maintenance_support_{index}")
                if maintenance_support_value:
                    maintenance_support.append({"value": maintenance_support_value, "is_checked": is_checked})

        # Yearly Maintenance Section
        for key in data.keys():
            if key.startswith("yearly_maintenance_check_"):
                index = key.split("_")[-1]
                is_checked = data.get(f"yearly_maintenance_check_{index}") == "1"
                yearly_maintenance_value = data.get(f"yearly_maintenance_{index}")
                if yearly_maintenance_value:
                    yearly_maintenance.append({"value": yearly_maintenance_value, "is_checked": is_checked})

        # Running Consumables Section
        for key in data.keys():
            if key.startswith("running_consumables_check_"):
                index = key.split("_")[-1]
                is_checked = data.get(f"running_consumables_check_{index}") == "1"
                running_consumables_value = data.get(f"running_consumables_{index}")
                if running_consumables_value:
                    running_consumables.append({"value": running_consumables_value, "is_checked": is_checked})

        # Exclusions Section
        for key in data.keys():
            if key.startswith("exclusions_check_"):
                index = key.split("_")[-1]
                is_checked = data.get(f"exclusions_check_{index}") == "1"
                exclusions_value = data.get(f"exclusions_{index}")
                if exclusions_value:
                    exclusions.append({"value": exclusions_value, "is_checked": is_checked})
        # AMC Pricing Section
        for key in data.keys():
            if key.startswith('select_amcp_check_'):
                index = key.split('_')[-1]
                is_checked = data.get(f'select_amcp_check_{index}') == "1"
                installation_data = {
                    'pd_name': data.get(f'pd_namep_{index}'),
                    'capacity': data.get(f'capacityp_{index}'),
                    'total_needed_capacity': data.get(f'total_needed_capacityp_{index}'),
                    'waste_water_type': data.get(f'waste_water_typep_{index}'),
                    'total_no_machines': data.get(f'total_no_machinesp_{index}'),
                    'is_checked': is_checked
                }
                amc_pricing.append(installation_data)
        for key in data.keys():
            if key.startswith('select_per_check_'):
                index = key.split('_')[-1]
                is_checked = data.get(f'select_per_check_{index}') == "1"
                installation_data = {
                    'particulars': data.get(f'particulars_{index}'),
                    'first_year_exgst': data.get(f'first_year_exgst_{index}'),
                    'is_checked': is_checked
                }
                Particulars.append(installation_data)

        # Terms Section
        for key in data.keys():
            if key.startswith("terms_check_"):
                index = key.split("_")[-1]
                is_checked = data.get(f"terms_check_{index}") == "1"
                terms_value = data.get(f"terms_{index}")
                if terms_value:
                    terms.append({"value": terms_value, "is_checked": is_checked})

        # Extract Subtotal
        if "content_select_sub" in data:
            is_checked = data.get("content_select_sub") == "on"  # Match "on" for checkbox behavior
            Subtotal_value = data.get("Subtotal1")
            if Subtotal_value:
                Subtotal_list.append({"value": Subtotal_value, "is_checked": is_checked})

        # Extract GST
        if "content_select_gst" in data:
            is_checked = data.get("content_select_gst") == "on"
            gst_value = data.get("gst1")
            if gst_value:
                GST.append({"value": gst_value, "is_checked": is_checked})

        # Extract Grand Total
        if "content_select_gtotal" in data:
            is_checked = data.get("content_select_gtotal") == "on"
            gtotal_value = data.get("grand")
            if gtotal_value:
                Grand_Total.append({"value": gtotal_value, "is_checked": is_checked})


        # Prepare the final data for saving
        final_data = {
            'quotation_number': quotation_number,
            'contents': contents,
            'terms': terms,
            'Amc_Proposal': Amc_Proposal,
            'maintenance_support': maintenance_support,
            'yearly_maintenance': yearly_maintenance,
            'running_consumables': running_consumables,
            'exclusions': exclusions,
            'amc_pricing': amc_pricing,
            'Particulars': Particulars,
            'Subtotal_list': Subtotal_list,
            'GST': GST,
            'Grand_Total': Grand_Total,
            'enquiry_id': enquiry_id,
        }

        # Store the final data in the file as JSON
        print(f"final",final_data)
        with open(file_path, "w") as json_file:
            json.dump(final_data, json_file, indent=4)
        logger.info("Data stored successfully at: %s", file_path)

        return JsonResponse(
            {"status": "success", "message": "Data stored successfully", "file_path": file_path}
        )

    except Exception as e:
        logger.error("An unexpected error occurred", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
    



####### draft_edit #############
import os
import json
import logging
from django.http import JsonResponse
from django.shortcuts import render
from django.conf import settings

logger = logging.getLogger(__name__)

def draft_edit_quotation(request, enquiry_id, quotation_number):
    logger.info("Editing Quotation: %s, %s", enquiry_id, quotation_number)

    # Define the file path for the quotation
    file_path = os.path.join(settings.BASE_DIR, "AMC_draft", str(enquiry_id), f"{quotation_number}.json")
    logger.debug(f"File path for quotation: {file_path}")

    # Check if the file exists
    if not os.path.exists(file_path):
        return JsonResponse({"status": "error", "message": "Quotation not found"}, status=404)

    # Load the existing quotation data from the file
    with open(file_path, "r") as json_file:
        quotation_data = json.load(json_file)

    if request.method == "POST":
        # Check if the request is triggered by the "Save as Draft" button
        if request.POST.get("save_draft_button") == "true":
            # Gather form data from the request
            data = request.POST
            logger.debug(f"Received data from form: {data}")

            # Initialize lists for data collection
            contents = []
            maintenance_support = []
            yearly_maintenance = []
            running_consumables = []
            Amc_Proposal = []
            exclusions = []
            amc_pricing = []
            Particulars = []
            Subtotal_list = []
            GST = []
            Grand_Total = []
            terms = []

            # Extract content data
            for key in data.keys():
                if key.startswith("content_select_"):
                    index = key.split("_")[-1]
                    content_select_value = data.get(f"content_select_{index}")
                    is_checked = content_select_value in ["1", "on", "true"]
                    content_value = data.get(f"content_{index}")
                    if content_value:
                        contents.append({"value": content_value, "is_checked": is_checked})

            # Amc_Proposal (Installations) Section
            for key in data.keys():
                if key.startswith('select_amc_check_'):
                    index = key.split('_')[-1]
                    is_checked = data.get(f'select_amc_check_{index}') == "1"
                    installation_data = {
                        'pd_name': data.get(f'pd_name_{index}'),
                        'capacity': data.get(f'capacity_{index}'),
                        'total_needed_capacity': data.get(f'total_needed_capacity_{index}'),
                        'waste_water_type': data.get(f'waste_water_type_{index}'),
                        'total_no_machines': data.get(f'total_no_machines_{index}'),
                        'is_checked': is_checked
                    }
                    Amc_Proposal.append(installation_data)

            # Inclusions Section
            for key in data.keys():
                if key.startswith("maintenance_support_check_"):
                    index = key.split("_")[-1]
                    is_checked = data.get(f"maintenance_support_check_{index}") == "1"
                    maintenance_support_value = data.get(f"maintenance_support_{index}")
                    if maintenance_support_value:
                        maintenance_support.append({"value": maintenance_support_value, "is_checked": is_checked})

            # Yearly Maintenance Section
            for key in data.keys():
                if key.startswith("yearly_maintenance_check_"):
                    index = key.split("_")[-1]
                    is_checked = data.get(f"yearly_maintenance_check_{index}") == "1"
                    yearly_maintenance_value = data.get(f"yearly_maintenance_{index}")
                    if yearly_maintenance_value:
                        yearly_maintenance.append({"value": yearly_maintenance_value, "is_checked": is_checked})

            # Running Consumables Section
            for key in data.keys():
                if key.startswith("running_consumables_check_"):
                    index = key.split("_")[-1]
                    is_checked = data.get(f"running_consumables_check_{index}") == "1"
                    running_consumables_value = data.get(f"running_consumables_{index}")
                    if running_consumables_value:
                        running_consumables.append({"value": running_consumables_value, "is_checked": is_checked})

            # Exclusions Section
            for key in data.keys():
                if key.startswith("exclusions_check_"):
                    index = key.split("_")[-1]
                    is_checked = data.get(f"exclusions_check_{index}") == "1"
                    exclusions_value = data.get(f"exclusions_{index}")
                    if exclusions_value:
                        exclusions.append({"value": exclusions_value, "is_checked": is_checked})

            # AMC Pricing Section
            for key in data.keys():
                if key.startswith('select_amcp_check_'):
                    index = key.split('_')[-1]
                    is_checked = data.get(f'select_amcp_check_{index}') == "1"
                    installation_data = {
                        'pd_name': data.get(f'pd_namep_{index}'),
                        'capacity': data.get(f'capacityp_{index}'),
                        'total_needed_capacity': data.get(f'total_needed_capacityp_{index}'),
                        'waste_water_type': data.get(f'waste_water_typep_{index}'),
                        'total_no_machines': data.get(f'total_no_machinesp_{index}'),
                        'is_checked': is_checked
                    }
                    amc_pricing.append(installation_data)

            for key in data.keys():
                if key.startswith('select_per_check_'):
                    index = key.split('_')[-1]
                    is_checked = data.get(f'select_per_check_{index}') == "1"
                    installation_data = {
                        'particulars': data.get(f'particulars_{index}'),
                        'first_year_exgst': data.get(f'first_year_exgst_{index}'),
                        'is_checked': is_checked
                    }
                    Particulars.append(installation_data)

            # Terms Section
            for key in data.keys():
                if key.startswith("terms_check_"):
                    index = key.split("_")[-1]
                    is_checked = data.get(f"terms_check_{index}") == "1"
                    terms_value = data.get(f"terms_{index}")
                    if terms_value:
                        terms.append({"value": terms_value, "is_checked": is_checked})

            # Extract Subtotal
            if "content_select_sub" in data:
                is_checked = data.get("content_select_sub") == "on"
                Subtotal_value = data.get("Subtotal1")
                if Subtotal_value:
                    Subtotal_list.append({"value": Subtotal_value, "is_checked": is_checked})

            # Extract GST
            if "content_select_gst" in data:
                is_checked = data.get("content_select_gst") == "on"
                gst_value = data.get("gst1")
                if gst_value:
                    GST.append({"value": gst_value, "is_checked": is_checked})

            # Extract Grand Total
            if "content_select_gtotal" in data:
                is_checked = data.get("content_select_gtotal") == "on"
                gtotal_value = data.get("grand")
                if gtotal_value:
                    Grand_Total.append({"value": gtotal_value, "is_checked": is_checked})

            # Define the directory and file path for saving the draft
            base_dir = os.path.join(settings.BASE_DIR, "AMC_draft", str(enquiry_id))
            os.makedirs(base_dir, exist_ok=True)

            # File path for overwriting the existing draft
            draft_file_path = os.path.join(base_dir, f"{quotation_number}.json")

            # Final data to save
            final_data = {
                'contents': contents,
                'terms': terms,
                'Amc_Proposal': Amc_Proposal,
                'maintenance_support': maintenance_support,
                'yearly_maintenance': yearly_maintenance,
                'running_consumables': running_consumables,
                'exclusions': exclusions,
                'amc_pricing': amc_pricing,
                'Particulars': Particulars,
                'Subtotal_list': Subtotal_list,
                'GST': GST,
                'Grand_Total': Grand_Total,
                'enquiry_id': enquiry_id,
                'quotation_number': quotation_number,
            }

            # Save or overwrite the draft file
            with open(draft_file_path, "w") as json_file:
                json.dump(final_data, json_file, indent=4)

            return JsonResponse({"status": "success", "message": "Draft saved successfully", "file": f"{quotation_number}.json"})
            
        # Check if the request is triggered by the "Save Changes" button
        elif request.POST.get("save_draft_button") == "false":
            try:
                # Move the file to the 'stored_data' directory
                stored_data_dir = os.path.join(settings.BASE_DIR, "stored_data", str(enquiry_id))
                os.makedirs(stored_data_dir, exist_ok=True)
                stored_data_file_path = os.path.join(stored_data_dir, f"{quotation_number}.json")

                # Move the file from AMC_draft to stored_data
                shutil.move(file_path, stored_data_file_path)

                # You can save any updated content for the quotation if needed, like before
                # Perform any further actions if necessary (like logging or updating fields)

                return JsonResponse({"status": "success", "message": "Changes saved and file moved successfully", "file": f"{quotation_number}.json"})

            except Exception as e:
                logger.error(f"Error while saving changes: {str(e)}")
                return JsonResponse({"status": "error", "message": str(e)}, status=500)

    # Render the template with the existing data for editing
    return render(request, 'xp2/draft_edit_quotation.html', {
        'quotation_data': quotation_data,
        'enquiry_id': enquiry_id,
        'quotation_number': quotation_number
    })





############################ proposal draft store ##################

def proposal_draft_store_data(request, enquiry_id, quotation_number):
    logger.info("Received request: %s", request.method)
    if request.method != "POST":
        print("entered the loop")
        return JsonResponse(
            {"status": "error", "message": "Only POST requests are allowed"}, status=405
        )
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse(
            {"status": "error", "message": "This request is not an AJAX request"},
            status=400,
        )
    try:
        # Handle FormData (request.POST and request.FILES)
        data = request.POST.dict()
        print(data)
        print("entered the loop 2")
        quotation_number = data.get("quotation_number") or proposal_get_quotation_number()
        if not quotation_number:
            return JsonResponse(
                {"status": "error", "message": "Quotation number is missing"},
                status=400,
            )

        # Define base directory for the enquiry_id
        base_dir = os.path.join(settings.BASE_DIR, "proposal_draft", str(enquiry_id))
        os.makedirs(base_dir, exist_ok=True)
        file_path = os.path.join(base_dir, f"{quotation_number}.json")

        base_dir1 = os.path.join(settings.BASE_DIR, "static", "process_diagrams", str(enquiry_id))
        os.makedirs(base_dir1, exist_ok=True)
        # Check if file already exists
        if os.path.exists(file_path):
            return JsonResponse(
                {"status": "error", "message": f"Quotation number {quotation_number} already exists for this enquiry"},
                status=400,
            )

        # Initialize lists to hold form data
        contents = []
        site_info=[]
        table_data = []
        treatment_processes = []
        observations_and_suggestions = []
        requirements_and_specifications = []
        specifications = []
        process_diagram = []
        process_description = []
        output_table = []
        pricing = []
        terms = []
        installation = []
        specification = []
        hardware = []
        general_terms_conditions = []
        appendix = []
        processed_indices = set()
        terms_indices=set()
        general_indices=set()
        processed_indices_supply_eq = set()  
        processed_indices_dristi = set() 
        


        for key in data.keys():
            if key.startswith("content_select_"):
                index = key.split("_")[-1]
                content_select_value = data.get(f"content_select_{index}")
                is_checked = content_select_value in ["1", "on", "true"]  
                content_value = data.get(f"content_{index}")
                print(f"content",content_value)
                if content_value:
                    contents.append({"value": content_value, "is_checked": is_checked})

        for key in data.keys():
            if key.startswith('site_select_info_'):
                index = key.split('_')[-1]
                site_data = {
                    'is_checked': data.get(f'site_select_info_{index}') == "1",
                    'info_text': data.get(f'site_info_{index}'),
                    'is_standard_checked': data.get(f'site_select_standard_{index}') == "1",
                    'standard_text': data.get(f'site_standard_{index}')
                }
                site_info.append(site_data)
        for key in data.keys():
            if key.startswith('sl_no_value_t1_'):
                # Extract the index of the current row from the key
                index = key.split('_')[-1]
                
                # Construct the row dictionary
                table_row = {
                    'sl_no': data.get(f'sl_no_value_t1_{index}'),
                    'raw_sewage_characteristics': data.get(f'raw_sewage_characteristics_value_t1_{index}'),
                    'unit': data.get(f'unit_value_t1_{index}'),
                    'value': data.get(f'value_value_t1_{index}'),
                    # Checkbox state: True if checked, False otherwise
                    'is_checked': data.get(f'select_row_t1_{index}') == "1"  # Check if the checkbox was checked
                }
                # Append the row to the table data list
                table_data.append(table_row)
        for key in data.keys():
            if key.startswith('standard_select_'):
                # Extract the index of the current row from the key
                index = key.split('_')[-1]
                
                # Construct the treatment process dictionary
                treatment_data = {
                    'is_checked': data.get(f'standard_select_{index}') == "1",  # Checkbox checked state
                    'principal_purpose_unit_process': data.get(f'principal_purpose_{index}'),  # Principal purpose
                    'unit_processes': data.get(f'unit_processes_{index}')  # Unit processes
                }
                
                # Append the treatment process data to the list
                treatment_processes.append(treatment_data)
        for key in data.keys():
            if key.startswith('observation_select_'):
                index = key.split('_')[-1]
                observation_data = {
                    'observation_checked': data.get(f'observation_select_{index}') == "1",
                    'observation': data.get(f'observation_{index}'),
                    'suggestion_checked': data.get(f'suggestion_select_{index}') == "1",
                    'suggestion': data.get(f'suggestion_{index}'),
                    'features_checked': data.get(f'features_select_{index}') == "1",
                    'features': data.get(f'features_{index}'),
                    'salient_checked': data.get(f'salient_select_{index}') == "1",
                    'salient': data.get(f'salient_{index}')
                }
                observations_and_suggestions.append(observation_data)
        # site_info.append({'observations_and_suggestions': observations_and_suggestions})
        for key in data.keys():
            if key.startswith('requirement_select_'):
                index = key.split('_')[-1]    
                requirement_data = {
                    'requirement_checked': data.get(f'requirement_select_{index}') == "1",
                    'requirement_text': data.get(f'requirement_{index}', '')
                }
                requirements_and_specifications.append(requirement_data)

        # requirements_and_specifications.append({'requirements_and_specifications': requirements_and_specifications})
        for key in data.keys():
            if key.startswith('spec_select_'):
                # Extract the index from the key
                index = key.split('_')[-1]
                
                # Construct the spec data dictionary
                spec_data = {
                    'spec_checked': data.get(f'spec_select_{index}') == "1",  # Checkbox checked state
                    'specs_for_25kld': data.get(f'specs_for_25kld_{index}', ''),  # Specs for 25 KLD
                    'hidrec': data.get(f'hidrec_{index}', '')  # HIDREC value
                }
                
                # Append the spec data to the specifications list
                specifications.append(spec_data)
        for key in data.keys():
            if key.startswith('process_diagram_'):
                # Extract the index from the key name
                index = key.split('_')[-1]

                process_diagram_checked = data.get(f'process_diagram_{index}') == "1"
                req_text = data.get(f'req_text_{index}', '')

                # Retrieve checkbox values to check if the images are selected
                process_diagram1_checked = data.get(f'process_diagram1_checked_{index}') == "1"
                process_diagram2_checked = data.get(f'process_diagram2_checked_{index}') == "1"

                # Retrieve uploaded files
                process_diagram1_file = request.FILES.get(f'process_diagram1_url_{index}', None)
                process_diagram2_file = request.FILES.get(f'process_diagram2_url_{index}', None)

                # Initialize variables for file paths
                process_diagram1_path = ''
                process_diagram2_path = ''

                # Save the file paths if checked
                if process_diagram1_checked and process_diagram1_file:
                    # Define the relative path for the process diagram 1 file
                    process_diagram1_path = os.path.join( "process_diagrams", str(enquiry_id), f"process_diagram1_{index}_{process_diagram1_file.name}")
                    process_diagram1_path = process_diagram1_path.replace("\\", "/")  # Normalize to forward slashes

                    # Save the file to the specified path inside static
                    with open(os.path.join(settings.BASE_DIR, process_diagram1_path), 'wb') as f:
                        for chunk in process_diagram1_file.chunks():
                            f.write(chunk)

                if process_diagram2_checked and process_diagram2_file:
                    # Define the relative path for the process diagram 2 file
                    process_diagram2_path = os.path.join("static", "process_diagrams", str(enquiry_id), f"process_diagram2_{index}_{process_diagram2_file.name}")
                    process_diagram2_path = process_diagram2_path.replace("\\", "/")  # Normalize to forward slashes

                    # Save the file to the specified path inside static
                    with open(os.path.join(settings.BASE_DIR, process_diagram2_path), 'wb') as f:
                        for chunk in process_diagram2_file.chunks():
                            f.write(chunk)

                # Gather the diagram data, including the file paths and checkbox statuses
                diagram_data = {
                    'process_diagram1_checked': process_diagram1_checked,
                    'process_diagram1_path': process_diagram1_path.replace("static/", ""),  # Remove 'static/' for cleaner paths
                    'process_diagram2_checked': process_diagram2_checked,
                    'process_diagram2_path': process_diagram2_path.replace("static/", ""),  # Remove 'static/' for cleaner paths
                    'process_diagram_checked': process_diagram_checked,
                    'req_text': req_text,
                }

                # Append the diagram data to the list
                process_diagram.append(diagram_data)
        for key in data.keys():
            if key.startswith("sl_no_value_op_"):
                index = key.split("_")[-1]
                
                # Check if the row is selected
                is_selected = data.get(f"select_row_op_{index}") == "1"
                
                # Retrieve other values
                sl_no = data.get(f"sl_no_value_op_{index}", "").strip()
                treated_water_characteristics = data.get(f"treated_water_characteristics_value_op_{index}", "").strip()
                unit = data.get(f"unit_value_op_{index}", "").strip()
                standard_value = data.get(f"standard_value_op_{index}", "").strip()
                
                # Only add rows with valid data or if explicitly selected
                if sl_no or treated_water_characteristics or unit or standard_value or is_selected:
                    output_row = {
                        'sl_no': sl_no,
                        'treated_water_characteristics': treated_water_characteristics,
                        'unit': unit,
                        'standard_value': standard_value,
                        'is_checked': is_selected
                    }
                    output_table.append({'output_data': output_row})
        for key in data.keys():
            if key.startswith("process_description_text_"):
                index = key.split("_")[-1]
                process_row = {

                    'process_description_checked': data.get(f"process_description_text_{index}") == "1",
                    'process_description': data.get(f"process_description_{index}"),

                    'is_checked': data.get(f'etp_text_{index}') == "1",
                    'etp_text': data.get(f'etp_text_value_{index}'),

                    'is_standard_checked': data.get(f'stp_text_{index}') == "1",
                    'stp_text': data.get(f'stp_text_value_{index}'),

                    'is_shs_checked': data.get(f'shs_text_{index}') == "1",
                    'shs_text': data.get(f'shs_text_value_{index}'),

                    'is_atm_checked': data.get(f'automation_text_{index}') == "1",
                    'automation_text': data.get(f'automation_text_value_{index}'),

                    'is_foot_checked': data.get(f'footprint_area_{index}') == "1",
                    'footprint_area': data.get(f'footprint_area_value_{index}'),

                    'is_tentative_checked': data.get(f'tentative_{index}') == "1",
                    'tentative_BOM': data.get(f'tentative__value_{index}'),
                }
                process_description.append({'process_data': process_row})
        for key in data.keys():
            if key.startswith("machine_cost_text_"):
                index = key.split("_")[-1]
                pricing_row = {
                    'machine_cost_text': data.get(f"machine_cost_value_{index}"),
                    'is_machine_checked': data.get(f"machine_cost_text_{index}") == "1"
                }
                pricing.append(pricing_row)

        for key in data.keys():
            if key.startswith("product_name_spe_"):
                index = key.split("_")[-1]
                installation_row = {
                    'product_name': data.get(f"product_name_spe_{index}", ""),
                    'capacity': data.get(f"capacity_value_spe_{index}", ""),
                    'total_needed_capacity': data.get(f"total_needed_capacity_value_spe_{index}", ""),
                    'waste_water_type': data.get(f"waste_water_type_value_spe_{index}", ""),
                    'total_no_machines': data.get(f"total_no_machines_value_spe_{index}", ""),
                    'is_checked': data.get(f"select_row_spe_{index}", "0") == "1"  # Checks if the checkbox is selected
                }
                installation.append(installation_row)

        for key in data.keys():
            if key.startswith("sl_no_value_det_"):
                index = key.split("_")[-1]
                specification_row = {
                    'sl_no': data.get(f"sl_no_value_det_{index}", ""),
                    'specification': data.get(f"specification_value_det_{index}", ""),
                    'qnty': data.get(f"qnty_value_det_{index}", ""),
                    'unit': data.get(f"unit_value_det_{index}", ""),
                    'unit_rate': data.get(f"unit_rate_value_det_{index}", ""),
                    'price_exgst': data.get(f"price_exgst_value_det_{index}", ""),
                    'total': data.get(f"total_value_det_{index}", ""),
                    'is_checked': data.get(f"select_row_det_{index}", "0") == "1"  # Checkbox value handling
                }
                specification.append(specification_row)

        for key in data.keys():
            if key.startswith("sl_no_value_opt_"):
                index = key.split("_")[-1]
                hardware_row = {
                    'sl_no': data.get(f"sl_no_value_opt_{index}", ""),
                    'optional_hardware': data.get(f"optional_hardware_value_opt_{index}", ""),
                    'qnty': data.get(f"qnty_value_opt_{index}", ""),
                    'unit': data.get(f"unit_value_opt_{index}", ""),
                    'unit_rate': data.get(f"unit_rate_value_opt_{index}", ""),
                    'price_exgst': data.get(f"price_exgst_value_opt_{index}", ""),
                    'total': data.get(f"total_value_opt_{index}", ""),
                    'is_checked': data.get(f"select_row_opt_{index}", "0") == "1"  # Handle checkbox state
                }
                hardware.append(hardware_row)

        for key in request.POST.keys():
            if key.startswith("terms_") and not key.startswith("terms_check_"):
                # Get the index from the key (e.g., "terms_1" -> "1")
                index = key.split("_")[1]

                # Retrieve the term text and checkbox status
                term_text = request.POST.get(f"terms_{index}")
                is_checked = request.POST.get(f"terms_check_{index}") == "1"

                # Append the term as a dictionary
                terms.append({
                    "text": term_text,
                    "is_checked": is_checked
                })

        for key in data.keys():
            if key.startswith('performance_'):
                index = key.split('_')[-1]

                # Skip if this index has already been processed
                if index in general_indices:
                    continue

                term_data = {
                    'performance_checked': data.get(f'performance_{index}') == "1",
                    'performance_text': data.get(f'performance_text_{index}'),

                    'flow_characteristics_checked': data.get(f'flow_characteristics_{index}') == "1",
                    'flow_characteristics_text': data.get(f'flow_characteristics_text_{index}'),

                    'trial_quality_check_checked': data.get(f'trial_quality_check_{index}') == "1",
                    'trial_quality_check_text': data.get(f'trial_quality_check_text_{index}'),

                    'virtual_completion_checked': data.get(f'virtual_completion_{index}') == "1",
                    'virtual_completion_text': data.get(f'virtual_completion_text_{index}'),

                    'limitation_liability_checked': data.get(f'limitation_liability_{index}') == "1",
                    'limitation_liability_text': data.get(f'limitation_liability_text_{index}'),

                    'force_clause_checked': data.get(f'force_clause_{index}') == "1",
                    'force_clause_text': data.get(f'force_clause_text_{index}'),

                    'additional_works_checked': data.get(f'additional_works_{index}') == "1",
                    'additional_works_text': data.get(f'additional_works_text_{index}'),

                    'warranty_guaranty_checked': data.get(f'warranty_guaranty_{index}') == "1",
                    'warranty_guaranty_text': data.get(f'warranty_guaranty_text_{index}'),

                    'arbitration_checked': data.get(f'arbitration_{index}') == "1",
                    'arbitration_text': data.get(f'arbitration_text_{index}'),

                    'validity_checked': data.get(f'validity_{index}') == "1",
                    'validity_text': data.get(f'validity_text_{index}')
                }

                # Add to the list only if it's not already present
                if term_data not in general_terms_conditions:
                    general_terms_conditions.append(term_data)

                # Mark this index as processed
                general_indices.add(index)

        
            for key in data.keys():
                if key.startswith('supply_eq_'):
                    index = key.split('_')[-1]
                    
                    if index in processed_indices_supply_eq:
                        continue

                    appendix_data = {
                        'supply_eq_checked': data.get(f'supply_eq_{index}') == "1",
                        'supply_eq_text': data.get(f'supply_eq_text_{index}'),
                        
                        'instal_commissioning_checked': data.get(f'instal_commissioning_{index}') == "1",
                        'instal_commissioning_text': data.get(f'instal_commissioning_text_{index}'),
                        
                        'clients_scope_checked': data.get(f'clients_scope_{index}') == "1",
                        'clients_scope_text': data.get(f'clients_scope_text_{index}'),
                        
                        'note_checked': data.get(f'note_{index}') == "1",
                        'note_text': data.get(f'note_text_{index}'),

                        'dristi_checked': data.get(f'dristi_{index}') == "1",
                        'dristi_subscription_text': data.get(f'dristi_subscription_{index}'),
                        
                        'iot_checked': data.get(f'iot_{index}') == "1",
                        'iot_hardware_text': data.get(f'iot_hardware_{index}'),

                        'dristi_checked': data.get(f'dristi_{index}') == "1",
                        'dristi_subscription_text': data.get(f'dristi_subscription_{index}'),
                        
                        'iot_checked': data.get(f'iot_{index}') == "1",
                        'iot_hardware_text': data.get(f'iot_hardware_{index}'),
                    }

                    if appendix_data not in appendix:
                        appendix.append(appendix_data)

                    processed_indices_supply_eq.add(index)
        final_data = {
            'quotation_number': quotation_number,
            'contents': contents,
            'site_info': site_info,
            'table_data': table_data,
            'treatment_processes': treatment_processes,
            'observations_and_suggestions': observations_and_suggestions,
            'requirements_and_specifications': requirements_and_specifications,
            'specifications': specifications,
            'process_diagram': process_diagram,
            'process_description': process_description,
            'output_table': output_table,
            'pricing': pricing,
            'installation': installation,
            'specification':specification,
            'hardware':hardware,
            'general_terms_conditions':general_terms_conditions,
            'appendix':appendix,
            'enquiry_id': enquiry_id,
            'terms':terms,
        }

        # Store the final data in the file as JSON
        with open(file_path, "w") as json_file:
            json.dump(final_data, json_file, indent=4)
        logger.info("Data stored successfully at: %s", file_path)
        for key, value in final_data.items():
            print(f"{key}: {value}")
        return JsonResponse(
            {"status": "success", "message": "Data stored successfully", "file_path": file_path}
        )

    except Exception as e:
        logger.error("An unexpected error occurred", exc_info=True)
        return JsonResponse({"status": "error", "message": str(e)}, status=500)
    


def draft_edit_quotation_pr(request, enquiry_id, quotation_number):
    logger.info("Editing Quotation: %s, %s", enquiry_id, quotation_number)

    # Define the file path for the existing quotation data (JSON file)
    file_path = os.path.join(settings.BASE_DIR, "proposal_draft", str(enquiry_id), f"{quotation_number}.json")
    print(f"path:", file_path)

    # Check if the file exists
    if not os.path.exists(file_path):
        return JsonResponse({"status": "error", "message": "Quotation not found"}, status=404)

    base_dir1 = os.path.join(settings.BASE_DIR, "process_diagrams", str(enquiry_id))
    os.makedirs(base_dir1, exist_ok=True)

    # Load the existing quotation data from the file
    with open(file_path, "r") as json_file:
        proposal_data = json.load(json_file)

    if request.method == "POST":
        print("entered")
        print(f"post",request.POST.get("save_draft_button"))
        # Check if the request is triggered by the "Save as Draft" button
        if request.POST.get("save_draft_button") == "true":
            print("draft")
            # Gather form data from the request
            data = request.POST
            print(data)
            logger.debug(f"Received data from form: {data}")
    
            contents = []
            site_info=[]
            table_data = []
            treatment_processes = []
            observations_and_suggestions = []
            requirements_and_specifications = []
            specifications = []
            process_diagram = []
            process_description = []
            output_table = []
            pricing = []
            terms = []
            installation = []
            specification = []
            hardware = []
            general_terms_conditions = []
            appendix = []
            processed_indices = set()
            terms_indices=set()
            general_indices=set()
            processed_indices_supply_eq = set()  
            processed_indices_dristi = set() 

            print("post received 2")
            for key in data.keys():
                print("post received 3")
                if key.startswith("content_select_"):
                    index = key.split("_")[-1]
                    content_select_value = data.get(f"content_select_{index}")
                    is_checked = content_select_value in ["1", "on", "true"]  
                    content_value = data.get(f"content_{index}")
                    print(f"content",content_value)
                    if content_value:
                        contents.append({"value": content_value, "is_checked": is_checked})

            for key in data.keys():
                if key.startswith('site_select_info_'):
                    index = key.split('_')[-1]
                    site_data = {
                        'is_checked': data.get(f'site_select_info_{index}') == "1",
                        'info_text': data.get(f'site_info_{index}'),
                        'is_standard_checked': data.get(f'site_select_standard_{index}') == "1",
                        'standard_text': data.get(f'site_standard_{index}')
                    }
                    site_info.append(site_data)
            for key in data.keys():
                if key.startswith('sl_no_value_t1_'):
                    # Extract the index of the current row from the key
                    index = key.split('_')[-1]
                    
                    # Construct the row dictionary
                    table_row = {
                        'sl_no': data.get(f'sl_no_value_t1_{index}'),
                        'raw_sewage_characteristics': data.get(f'raw_sewage_characteristics_value_t1_{index}'),
                        'unit': data.get(f'unit_value_t1_{index}'),
                        'value': data.get(f'value_value_t1_{index}'),
                        # Checkbox state: True if checked, False otherwise
                        'is_checked': data.get(f'select_row_t1_{index}') == "1"  # Check if the checkbox was checked
                    }
                    # Append the row to the table data list
                    table_data.append(table_row)
            for key in data.keys():
                if key.startswith('standard_select_'):
                    # Extract the index of the current row from the key
                    index = key.split('_')[-1]
                    
                    # Construct the treatment process dictionary
                    treatment_data = {
                        'is_checked': data.get(f'standard_select_{index}') == "1",  # Checkbox checked state
                        'principal_purpose_unit_process': data.get(f'principal_purpose_{index}'),  # Principal purpose
                        'unit_processes': data.get(f'unit_processes_{index}')  # Unit processes
                    }
                    
                    # Append the treatment process data to the list
                    treatment_processes.append(treatment_data)
            for key in data.keys():
                if key.startswith('observation_select_'):
                    index = key.split('_')[-1]
                    observation_data = {
                        'observation_checked': data.get(f'observation_select_{index}') == "1",
                        'observation': data.get(f'observation_{index}'),
                        'suggestion_checked': data.get(f'suggestion_select_{index}') == "1",
                        'suggestion': data.get(f'suggestion_{index}'),
                        'features_checked': data.get(f'features_select_{index}') == "1",
                        'features': data.get(f'features_{index}'),
                        'salient_checked': data.get(f'salient_select_{index}') == "1",
                        'salient': data.get(f'salient_{index}')
                    }
                    observations_and_suggestions.append(observation_data)
            # site_info.append({'observations_and_suggestions': observations_and_suggestions})
            for key in data.keys():
                if key.startswith('requirement_select_'):
                    index = key.split('_')[-1]    
                    requirement_data = {
                        'requirement_checked': data.get(f'requirement_select_{index}') == "1",
                        'requirement_text': data.get(f'requirement_{index}', '')
                    }
                    requirements_and_specifications.append(requirement_data)

            # requirements_and_specifications.append({'requirements_and_specifications': requirements_and_specifications})
            for key in data.keys():
                if key.startswith('spec_select_'):
                    # Extract the index from the key
                    index = key.split('_')[-1]
                    
                    # Construct the spec data dictionary
                    spec_data = {
                        'spec_checked': data.get(f'spec_select_{index}') == "1",  # Checkbox checked state
                        'specs_for_25kld': data.get(f'specs_for_25kld_{index}', ''),  # Specs for 25 KLD
                        'hidrec': data.get(f'hidrec_{index}', '')  # HIDREC value
                    }
                    
                    # Append the spec data to the specifications list
                    specifications.append(spec_data)
            for key in data.keys():
                if key.startswith('process_diagram_'):
                    # Extract the index from the key name
                    index = key.split('_')[-1]

                    process_diagram_checked = data.get(f'process_diagram_{index}') == "1"
                    req_text = data.get(f'req_text_{index}', '')

                    # Retrieve checkbox values to check if the images are selected
                    process_diagram1_checked = data.get(f'process_diagram1_checked_{index}') == "1"
                    process_diagram2_checked = data.get(f'process_diagram2_checked_{index}') == "1"

                    # Retrieve uploaded files
                    process_diagram1_file = request.FILES.get(f'process_diagram1_url_{index}', None)
                    process_diagram2_file = request.FILES.get(f'process_diagram2_url_{index}', None)

                    # Initialize variables for file paths
                    process_diagram1_path = ''
                    process_diagram2_path = ''

                    # Save the file paths if checked
                    if process_diagram1_checked and process_diagram1_file:
                        # Define the relative path for the process diagram 1 file
                        process_diagram1_path = os.path.join("static", "process_diagrams", str(enquiry_id), f"process_diagram1_{index}_{process_diagram1_file.name}")
                        process_diagram1_path = process_diagram1_path.replace("\\", "/")  # Normalize to forward slashes

                        # Save the file to the specified path inside static
                        with open(os.path.join(settings.BASE_DIR, process_diagram1_path), 'wb') as f:
                            for chunk in process_diagram1_file.chunks():
                                f.write(chunk)

                    if process_diagram2_checked and process_diagram2_file:
                        # Define the relative path for the process diagram 2 file
                        process_diagram2_path = os.path.join("static", "process_diagrams", str(enquiry_id), f"process_diagram2_{index}_{process_diagram2_file.name}")
                        process_diagram2_path = process_diagram2_path.replace("\\", "/")  # Normalize to forward slashes

                        # Save the file to the specified path inside static
                        with open(os.path.join(settings.BASE_DIR, process_diagram2_path), 'wb') as f:
                            for chunk in process_diagram2_file.chunks():
                                f.write(chunk)

                    # Gather the diagram data, including the file paths and checkbox statuses
                    diagram_data = {
                        'process_diagram1_checked': process_diagram1_checked,
                        'process_diagram1_path': process_diagram1_path.replace("static/", ""),  # Remove 'static/' for cleaner paths
                        'process_diagram2_checked': process_diagram2_checked,
                        'process_diagram2_path': process_diagram2_path.replace("static/", ""),  # Remove 'static/' for cleaner paths
                        'process_diagram_checked': process_diagram_checked,
                        'req_text': req_text,
                    }

                    # Append the diagram data to the list
                    process_diagram.append(diagram_data)
            for key in data.keys():
                if key.startswith("sl_no_value_op_"):
                    index = key.split("_")[-1]
                    
                    # Check if the row is selected
                    is_selected = data.get(f"select_row_op_{index}") == "1"
                    
                    # Retrieve other values
                    sl_no = data.get(f"sl_no_value_op_{index}", "").strip()
                    treated_water_characteristics = data.get(f"treated_water_characteristics_value_op_{index}", "").strip()
                    unit = data.get(f"unit_value_op_{index}", "").strip()
                    standard_value = data.get(f"standard_value_op_{index}", "").strip()
                    
                    # Only add rows with valid data or if explicitly selected
                    if sl_no or treated_water_characteristics or unit or standard_value or is_selected:
                        output_row = {
                            'sl_no': sl_no,
                            'treated_water_characteristics': treated_water_characteristics,
                            'unit': unit,
                            'standard_value': standard_value,
                            'is_checked': is_selected
                        }
                        output_table.append({'output_data': output_row})
            for key in data.keys():
                if key.startswith("process_description_text_"):
                    index = key.split("_")[-1]
                    process_row = {

                        'process_description_checked': data.get(f"process_description_text_{index}") == "1",
                        'process_description': data.get(f"process_description_{index}"),

                        'is_checked': data.get(f'etp_text_{index}') == "1",
                        'etp_text': data.get(f'etp_text_value_{index}'),

                        'is_standard_checked': data.get(f'stp_text_{index}') == "1",
                        'stp_text': data.get(f'stp_text_value_{index}'),

                        'is_shs_checked': data.get(f'shs_text_{index}') == "1",
                        'shs_text': data.get(f'shs_text_value_{index}'),

                        'is_atm_checked': data.get(f'automation_text_{index}') == "1",
                        'automation_text': data.get(f'automation_text_value_{index}'),

                        'is_foot_checked': data.get(f'footprint_area_{index}') == "1",
                        'footprint_area': data.get(f'footprint_area_value_{index}'),

                        'is_tentative_checked': data.get(f'tentative_{index}') == "1",
                        'tentative_BOM': data.get(f'tentative__value_{index}'),
                    }
                    process_description.append({'process_data': process_row})
            for key in data.keys():
                if key.startswith("machine_cost_text_"):
                    index = key.split("_")[-1]
                    pricing_row = {
                        'machine_cost_text': data.get(f"machine_cost_value_{index}"),
                        'is_machine_checked': data.get(f"machine_cost_text_{index}") == "1"
                    }
                    pricing.append(pricing_row)

            for key in data.keys():
                if key.startswith("product_name_spe_"):
                    index = key.split("_")[-1]
                    installation_row = {
                        'product_name': data.get(f"product_name_spe_{index}", ""),
                        'capacity': data.get(f"capacity_value_spe_{index}", ""),
                        'total_needed_capacity': data.get(f"total_needed_capacity_value_spe_{index}", ""),
                        'waste_water_type': data.get(f"waste_water_type_value_spe_{index}", ""),
                        'total_no_machines': data.get(f"total_no_machines_value_spe_{index}", ""),
                        'is_checked': data.get(f"select_row_spe_{index}", "0") == "1"  # Checks if the checkbox is selected
                    }
                    installation.append(installation_row)

            for key in data.keys():
                if key.startswith("sl_no_value_det_"):
                    index = key.split("_")[-1]
                    specification_row = {
                        'sl_no': data.get(f"sl_no_value_det_{index}", ""),
                        'specification': data.get(f"specification_value_det_{index}", ""),
                        'qnty': data.get(f"qnty_value_det_{index}", ""),
                        'unit': data.get(f"unit_value_det_{index}", ""),
                        'unit_rate': data.get(f"unit_rate_value_det_{index}", ""),
                        'price_exgst': data.get(f"price_exgst_value_det_{index}", ""),
                        'total': data.get(f"total_value_det_{index}", ""),
                        'is_checked': data.get(f"select_row_det_{index}", "0") == "1"  # Checkbox value handling
                    }
                    specification.append(specification_row)

            for key in data.keys():
                if key.startswith("sl_no_value_opt_"):
                    index = key.split("_")[-1]
                    hardware_row = {
                        'sl_no': data.get(f"sl_no_value_opt_{index}", ""),
                        'optional_hardware': data.get(f"optional_hardware_value_opt_{index}", ""),
                        'qnty': data.get(f"qnty_value_opt_{index}", ""),
                        'unit': data.get(f"unit_value_opt_{index}", ""),
                        'unit_rate': data.get(f"unit_rate_value_opt_{index}", ""),
                        'price_exgst': data.get(f"price_exgst_value_opt_{index}", ""),
                        'total': data.get(f"total_value_opt_{index}", ""),
                        'is_checked': data.get(f"select_row_opt_{index}", "0") == "1"  # Handle checkbox state
                    }
                    hardware.append(hardware_row)

            for key in request.POST.keys():
                if key.startswith("terms_") and not key.startswith("terms_check_"):
                    # Get the index from the key (e.g., "terms_1" -> "1")
                    index = key.split("_")[1]

                    # Retrieve the term text and checkbox status
                    term_text = request.POST.get(f"terms_{index}")
                    is_checked = request.POST.get(f"terms_check_{index}") == "1"

                    # Append the term as a dictionary
                    terms.append({
                        "text": term_text,
                        "is_checked": is_checked
                    })

            for key in data.keys():
                if key.startswith('performance_'):
                    index = key.split('_')[-1]

                    # Skip if this index has already been processed
                    if index in general_indices:
                        continue

                    term_data = {
                        'performance_checked': data.get(f'performance_{index}') == "1",
                        'performance_text': data.get(f'performance_text_{index}'),

                        'flow_characteristics_checked': data.get(f'flow_characteristics_{index}') == "1",
                        'flow_characteristics_text': data.get(f'flow_characteristics_text_{index}'),

                        'trial_quality_check_checked': data.get(f'trial_quality_check_{index}') == "1",
                        'trial_quality_check_text': data.get(f'trial_quality_check_text_{index}'),

                        'virtual_completion_checked': data.get(f'virtual_completion_{index}') == "1",
                        'virtual_completion_text': data.get(f'virtual_completion_text_{index}'),

                        'limitation_liability_checked': data.get(f'limitation_liability_{index}') == "1",
                        'limitation_liability_text': data.get(f'limitation_liability_text_{index}'),

                        'force_clause_checked': data.get(f'force_clause_{index}') == "1",
                        'force_clause_text': data.get(f'force_clause_text_{index}'),

                        'additional_works_checked': data.get(f'additional_works_{index}') == "1",
                        'additional_works_text': data.get(f'additional_works_text_{index}'),

                        'warranty_guaranty_checked': data.get(f'warranty_guaranty_{index}') == "1",
                        'warranty_guaranty_text': data.get(f'warranty_guaranty_text_{index}'),

                        'arbitration_checked': data.get(f'arbitration_{index}') == "1",
                        'arbitration_text': data.get(f'arbitration_text_{index}'),

                        'validity_checked': data.get(f'validity_{index}') == "1",
                        'validity_text': data.get(f'validity_text_{index}')
                    }

                    # Add to the list only if it's not already present
                    if term_data not in general_terms_conditions:
                        general_terms_conditions.append(term_data)

                    # Mark this index as processed
                    general_indices.add(index)
            for key in data.keys():
                if key.startswith('supply_eq_'):
                    index = key.split('_')[-1]
                    
                    if index in processed_indices_supply_eq:
                        continue

                    appendix_data = {
                        'supply_eq_checked': data.get(f'supply_eq_{index}') == "1",
                        'supply_eq_text': data.get(f'supply_eq_text_{index}'),
                        
                        'instal_commissioning_checked': data.get(f'instal_commissioning_{index}') == "1",
                        'instal_commissioning_text': data.get(f'instal_commissioning_text_{index}'),
                        
                        'clients_scope_checked': data.get(f'clients_scope_{index}') == "1",
                        'clients_scope_text': data.get(f'clients_scope_text_{index}'),
                        
                        'note_checked': data.get(f'note_{index}') == "1",
                        'note_text': data.get(f'note_text_{index}'),

                        'dristi_checked': data.get(f'dristi_{index}') == "1",
                        'dristi_subscription_text': data.get(f'dristi_subscription_{index}'),
                        
                        'iot_checked': data.get(f'iot_{index}') == "1",
                        'iot_hardware_text': data.get(f'iot_hardware_{index}'),

                        'dristi_checked': data.get(f'dristi_{index}') == "1",
                        'dristi_subscription_text': data.get(f'dristi_subscription_{index}'),
                        
                        'iot_checked': data.get(f'iot_{index}') == "1",
                        'iot_hardware_text': data.get(f'iot_hardware_{index}'),
                    }

                    if appendix_data not in appendix:
                        appendix.append(appendix_data)

                    processed_indices_supply_eq.add(index)

            base_dir = os.path.join(settings.BASE_DIR, "proposal_draft", str(enquiry_id))
            os.makedirs(base_dir, exist_ok=True)

                        # File path for overwriting the existing draft
            draft_file_path = os.path.join(base_dir, f"{quotation_number}.json")
            # Save the edited data to the new versioned file
            final_data = {
                    'quotation_number': quotation_number,
                    'contents': contents,
                    'site_info': site_info,
                    'table_data': table_data,
                    'treatment_processes': treatment_processes,
                    'observations_and_suggestions': observations_and_suggestions,
                    'requirements_and_specifications': requirements_and_specifications,
                    'specifications': specifications,
                    'process_diagram': process_diagram,
                    'process_description': process_description,
                    'output_table': output_table,
                    'pricing': pricing,
                    'installation': installation,
                    'specification':specification,
                    'hardware':hardware,
                    'general_terms_conditions':general_terms_conditions,
                    'appendix':appendix,
                    'enquiry_id': enquiry_id,
                    'terms':terms,
                }
        # Save or overwrite the draft file
            with open(draft_file_path, "w") as json_file:
                json.dump(final_data, json_file, indent=4)

            return JsonResponse({"status": "success", "message": "Draft saved successfully", "file": f"{quotation_number}.json"})

        # Check if the request is triggered by the "Save Changes" button
        elif request.POST.get("save_draft_button") == "false":
            print("normal")
            try:
                # Move the file to the 'stored_data' directory
                stored_data_dir = os.path.join(settings.BASE_DIR, "proposal", str(enquiry_id))
                os.makedirs(stored_data_dir, exist_ok=True)
                stored_data_file_path = os.path.join(stored_data_dir, f"{quotation_number}.json")

                # Move the file from proposal_draft to stored_data
                shutil.move(file_path, stored_data_file_path)

                # You can save any updated content for the quotation if needed
                # Perform any further actions if necessary (like logging or updating fields)

                return JsonResponse({"status": "success", "message": "Changes saved and file moved successfully", "file": f"{quotation_number}.json"})

            except Exception as e:
                logger.error(f"Error while saving changes: {str(e)}")
                return JsonResponse({"status": "error", "message": str(e)}, status=500)

    # Return the template with the existing data for editing
    data_json = json.dumps(proposal_data)
    return render(request, 'xp2/draft_proposal_edit.html', {'proposal_data': proposal_data, 'data': data_json})


from .views import RevertRemark

def export_pdf_details(request, enquiry_id):
    try:
        enquiry_data = get_object_or_404(Enquiry, id=enquiry_id)
        revert_remarks = enquiry_data.revert_remarks.all()  # Access related revert remarks
        followups = enquiry_data.followups.all()  # Access related follow-ups using the correct related_name
    except Enquiry.DoesNotExist:
        return HttpResponse("Enquiry not found.", status=404)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="enquiry_{enquiry_id}_details.pdf"'

    pdf_canvas = canvas.Canvas(response, pagesize=letter)
    width, height = letter
    y = height - 50

    # Header
    pdf_canvas.setFont("Helvetica-Bold", 16)
    pdf_canvas.drawString(200, y, "Enquiry Details Report")
    y -= 40

    pdf_canvas.setFont("Helvetica", 12)

    # Enquiry Details
    details = [
        f"Company Name: {enquiry_data.companyname}",
        f"Customer Name: {enquiry_data.customername}",
        f"Reference: {enquiry_data.refrence}",
        f"Email: {enquiry_data.email}",
        f"Contact: {enquiry_data.contact}",
        f"Location: {enquiry_data.location}",
        f"Status: {enquiry_data.status}",
        f"Products: {enquiry_data.products}",
        f"Sub Product: {enquiry_data.subproduct}",
        f"Closure Date: {enquiry_data.closuredate}",
        f"Executive: {enquiry_data.executive}",
        f"Remarks: {enquiry_data.remarks}",
    ]
    for detail in details:
        if y < 50:
            pdf_canvas.showPage()
            y = height - 50
        pdf_canvas.drawString(50, y, detail)
        y -= 15

    # Revert Remarks
    if y < 70:
        pdf_canvas.showPage()
        y = height - 50
    pdf_canvas.setFont("Helvetica-Bold", 12)
    pdf_canvas.drawString(50, y, "Revert Remarks:")
    y -= 20

    pdf_canvas.setFont("Helvetica", 10)
    if revert_remarks.exists():
        for remark in revert_remarks:
            if y < 50:
                pdf_canvas.showPage()
                y = height - 50
            pdf_canvas.drawString(50, y, f"- {remark.text} ({remark.created_at})")
            y -= 15
    else:
        pdf_canvas.drawString(50, y, "No revert remarks available.")
        y -= 15

    # Follow-Ups
    if y < 70:
        pdf_canvas.showPage()
        y = height - 50
    pdf_canvas.setFont("Helvetica-Bold", 12)
    pdf_canvas.drawString(50, y, "Follow-Up History:")
    y -= 20

    pdf_canvas.setFont("Helvetica", 10)
    if followups.exists():
        for followup in followups:
            if y < 50:
                pdf_canvas.showPage()
                y = height - 50
            pdf_canvas.drawString(50, y, f"- Name: {followup.foname}, Date: {followup.fodate}, Time: {followup.fotime}")
            y -= 15
    else:
        pdf_canvas.drawString(50, y, "No follow-ups recorded.")
        y -= 15

    # Files
    if y < 70:
        pdf_canvas.showPage()
        y = height - 50
    pdf_canvas.setFont("Helvetica-Bold", 12)
    pdf_canvas.drawString(50, y, "Attached Files:")
    y -= 20

    pdf_canvas.setFont("Helvetica", 10)
    if enquiry_data.files.exists():
        for file in enquiry_data.files.all():
            if y < 50:
                pdf_canvas.showPage()
                y = height - 50
            pdf_canvas.drawString(50, y, f"- {file.name}: {file.file.url}")
            y -= 15
    else:
        pdf_canvas.drawString(50, y, "No files uploaded.")
        y -= 15

    # Save and return response
    pdf_canvas.showPage()
    pdf_canvas.save()

    return response



def export_confirmed_orders_pdf(request):
    # Get the search query from GET request
    search_query = request.GET.get('search', '')

    # Filter confirmed orders based on search query
    confirmed_orders = ConfirmedOrder.objects.all()
    if search_query:
        confirmed_orders = confirmed_orders.filter(companyname__icontains=search_query)  # Adjust filter as needed

    # Pagination logic (optional)
    paginator = Paginator(confirmed_orders, 10)  # Show 10 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Render the template with the filtered and paginated data
    html = render_to_string('xp2/confirmed_orders_pdf_template.html', {'confirmed_orders': page_obj.object_list})

    # Create a PDF response using xhtml2pdf
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="confirmed_orders.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)

    return response


import re
from django.utils.timezone import now

def hidrec_wash(request, enquiry_id):
    hid = Hidrec_wash.objects.all()

    if request.method == "POST":
        current_date = now()
        yy_mm = current_date.strftime("%y%m")  # Example: '2404'

        # Fetch the last quotation starting with HIDREC-WASH-YYMM
        last_entry = ConfirmedHidrecWash.objects.filter(
            quotation_no__startswith=f"HIDREC-WASH-{yy_mm}"
        ).order_by('-quotation_no').first()

        new_number = 1  # Default starting number

        if last_entry:
            # Extract the number part after 'HIDREC-WASH-YYMM'
            match = re.search(rf'HIDREC-WASH-{yy_mm}(\d+)', last_entry.quotation_no)
            if match:
                new_number = int(match.group(1)) + 1

        quotation_no = f"HIDREC-WASH-{yy_mm}{new_number:03d}"

        # Save new record
        ConfirmedHidrecWash.objects.create(
            enquiry_id=enquiry_id,
            quotation_no=quotation_no,
            contents=request.POST.get("hi_contents", ""),
            hidrec_wash_text=request.POST.get("wash_texts", ""),
            price=request.POST.get("price", ""),
            carwash_text=request.POST.get("car_texts", ""),
            priceoil_skimmer=request.POST.get("price_oil", ""),
            specification=request.POST.get("specifications", ""),
            terms_conditions=request.POST.get("terms&condition", ""),
            general_maintenance=request.POST.get("general", ""),
            total_price=request.POST.get("total", ""),
        )

        return redirect('managequotationpage', enquiry_id=enquiry_id)

    return render(request, 'xp2/hidrec_wash.html', {'enquiry_id': enquiry_id, 'hid': hid})




def hidrecwash_preview(request,quotation_no):
    hidrec=ConfirmedHidrecWash.objects.filter(quotation_no=quotation_no)
    company = companydetails.objects.all()
    current_date = datetime.now().strftime('%d %b, %Y')


    return render(request,'xp2/hidrecwash_preview.html',{'hidrec':hidrec,'company':company,'current_date':current_date})


import re
from django.shortcuts import render, redirect
from .models import ConfirmedHidrecWash

def edit_hidrecwash(request, quotation_no, enquiry_id):
    # Fetch existing records matching the quotation_no
    hidrec = ConfirmedHidrecWash.objects.filter(quotation_no=quotation_no)

    if request.method == 'POST':
        # Clean the quotation_no to get base (remove trailing R1, R2, etc.)
        base_quotation_no = re.sub(r'R\d+$', '', quotation_no)

        # Get latest revision (if any) for the same base
        latest_entry = ConfirmedHidrecWash.objects.filter(
            quotation_no__startswith=base_quotation_no
        ).order_by('-quotation_no').first()

        rev_num = 1  # Default if no revision exists

        if latest_entry:
            match = re.search(r'R(\d+)$', latest_entry.quotation_no)
            if match:
                rev_num = int(match.group(1)) + 1

        # Construct new quotation number with revision suffix
        new_quotation_no = f"{base_quotation_no}R{rev_num}"

        # Use only the first matched record for data population
        old_record = hidrec.first()

        if old_record:
            # Save the new record with the updated data
            ConfirmedHidrecWash.objects.create(
                enquiry_id=enquiry_id,
                quotation_no=new_quotation_no,
                contents=request.POST.get("hi_contents", old_record.contents),
                hidrec_wash_text=request.POST.get("wash_texts", old_record.hidrec_wash_text),
                price=request.POST.get("price", old_record.price),
                carwash_text=request.POST.get("car_texts", old_record.carwash_text),
                priceoil_skimmer=request.POST.get("price_oil", old_record.priceoil_skimmer),
                specification=request.POST.get("specifications", old_record.specification),
                terms_conditions=request.POST.get("terms&condition", old_record.terms_conditions),
                general_maintenance=request.POST.get("general", old_record.general_maintenance),
                total_price=request.POST.get("total", old_record.total_price)
            )

        return redirect('managequotationpage', enquiry_id=enquiry_id)

    return render(request, 'xp2/edit_hidrecwash.html', {
        'quotation_no': quotation_no,
        'enquiry_id': enquiry_id,
        'hidrec': hidrec
    })





from .models import UploadedQuote
import uuid

def upload_quote(request, enquiry_id):
    if request.method == 'POST':
        enquiry = get_object_or_404(Enquiry, id=enquiry_id)
        
        quote_types = request.POST.getlist('quote_type[]')
        quote_files = request.FILES.getlist('quote_file[]')
        
        if not quote_types:
            quote_types = request.POST.getlist('quote_type')
            quote_files = request.FILES.getlist('quote_file')

        uploaded_count = 0
        for q_type, q_file in zip(quote_types, quote_files):
            if q_type and q_file:
                quotation_no = f"UP-{q_type[:3].upper()}-{uuid.uuid4().hex[:6].upper()}"
                UploadedQuote.objects.create(
                    enquiry=enquiry,
                    quote_type=q_type,
                    file=q_file,
                    quotation_no=quotation_no
                )
                uploaded_count += 1
                
        if uploaded_count > 0:
            messages.success(request, f"{uploaded_count} document(s) successfully uploaded.")
        else:
            messages.error(request, "Please provide valid files and quote types.")
            
    return redirect('managequotationpage', enquiry_id=enquiry_id)
