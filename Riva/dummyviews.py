import json
import shutil
from django.shortcuts import render,redirect
from django.http import JsonResponse,HttpResponse
from .models import ConfirmedHidrecWash, ConfirmedOrderFollowUp, Enquiry, Hidrec_wash,Products,Executive,FileUploadModel, quotation, ConfirmedOrder,FollowUp,companydetails
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
    if  current_user.is_staff or current_user.is_superuser:
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


def enq_home(request):
    current_user = request.user
    selected_user_id = request.GET.get('user')
    selected_user = None

    if selected_user_id:
        selected_user = User.objects.filter(id=selected_user_id).first()
        # Managers/superusers see all enquiries (non-confirmed, non-lost, or reverted)
        enquiries = Enquiry.objects.filter(
            Q(is_confirmed=False, is_lost=False) | Q(is_reverted=True)
        )
    else:
        # Other users see their own created or assigned enquiries (non-confirmed, non-lost, or reverted)
        enquiries = Enquiry.objects.filter(
            Q(is_confirmed=False, is_lost=False) | Q(is_reverted=True)
        ).filter(
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
        enquiries = enquiries.filter(global_filter).order_by('-id')
    else:
        enquiries = enquiries.order_by('-id')

    # Pagination setup
    paginator = Paginator(enquiries, 10)  # 10 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Add a sequence number for display in the template
    start_sequence_number = (page_obj.number - 1) * paginator.per_page + 1
    for index, enquiry in enumerate(page_obj, start=start_sequence_number):
        enquiry.sequence_number = index

    # Render the response
    return render(request, 'xp/enqhome.html', {
        'page_obj': page_obj,
        'search_query': search_query
    })



   

def enquiry_view(request):
    executive=Executive.objects.all()
    products=Products.objects.all()
    return render(request, 'xp/newenquiry.html',{'products':products , 'executive':executive})

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
        remarks = request.POST.get("remarks")
        files = request.FILES.getlist("attachment[]")

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
            return render(request, 'xp/newenquiry.html', {
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

        return render(request, 'xp/enquiry_details.html', {'enquiry_data': data, 'followups': followups , 'revert_remarks': revert_remarks})

    except Enquiry.DoesNotExist:
        return HttpResponse("Enquiry not found", status=404)

    

from .forms import EnquiryForm

def edit_enquiry(request, enquiry_id): 
    enquiry = get_object_or_404(Enquiry, id=enquiry_id)
    
    if request.method == "POST":
        form = EnquiryForm(request.POST, request.FILES, instance=enquiry)

        if form.is_valid():
            # Access the 'products' field from form.cleaned_data after validation
            products = form.cleaned_data.get('products')  
            print(f"Products: {products}")

            # Save the changes to the database
            form.save()

            # Handle file uploads (if any)
            files = request.FILES.getlist("attachment[]")  # Get files from the request
            for file in files:
                # Create a FileUploadModel instance for each uploaded file
                file_upload = FileUploadModel.objects.create(file=file, name=file.name)
                enquiry.files.add(file_upload)  # Add the file to the Many-to-Many relationship

            # Save the enquiry after adding the files
            enquiry.save()

            # Display a success message and redirect
            messages.success(request, "Enquiry updated successfully!")
            return redirect('enquries')  # Redirect to enquiry homepage
        else:
            # Display error message if form is invalid
            messages.error(request, "There was an error updating the enquiry. Please fix the errors below.")
            print(form.errors)  # Log the errors for debugging
    else:
        # Display the form for GET request
        form = EnquiryForm(instance=enquiry)

    return render(request, 'xp/edit_enquiry.html', {'form': form, 'enquiry_id': enquiry_id})




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
    if selected_user_id:
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
    if  current_user.is_staff or current_user.is_superuser:
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
    return render(request, 'xp/lost_orders.html', {
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
    enquiry.is_reverted=True
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
    return render(request, 'xp/manage_quotation.html', {
        'enquiry': enquiry,
        'hidrec':hidrec,
        'quotations': quotations,
        'stored_data': dict(stored_data),  # Convert defaultdict to a standard dict for the template
        'proposal_data': dict(proposal_data),
        'draft_data':dict(draft_data),
        'proposal_draft_data':dict(proposal_draft_data),
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
    
#     return render(request, 'xp/manage_quotation.html', {
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
    return render(request, 'xp/quotation_details.html', {
        'quotations': quotations,
        'enquiry': enquiry,
        'files': files,  # Pass the files to the template
        'boq_file_name': boq_file_name,
        'quote_file_name': quote_file_name,
    })



from .models import confirmed_enquiry

def confirm_order(request, enquiry_id):
    enquiry = get_object_or_404(Enquiry, id=enquiry_id)
    quotations = CommercialQuote.objects.filter(enquiry_id=enquiry_id).order_by('-id')
    hidrec=ConfirmedHidrecWash.objects.filter(enquiry_id=enquiry_id).order_by('-id')

    # Get all confirmed quotations for this enquiry
    confirmed_quotations = confirmed_enquiry.objects.filter(
        enquiry=enquiry
    ).values_list('quotation', flat=True)

    # Initialize file paths for 'stored_data' and 'proposal'
    base_dir = settings.BASE_DIR
    stored_data_path = os.path.join(base_dir, 'stored_data')
    proposal_path = os.path.join(base_dir, 'proposal')

    # Prepare data for stored_data and proposal
    all_stored_files = []
    all_proposal_files = []
    stored_data = defaultdict(list)
    proposal_data = defaultdict(list)

    # Load 'stored_data'
    stored_data_directories = os.listdir(stored_data_path)
    for directory in stored_data_directories:
        dir_path = os.path.join(stored_data_path, directory)
        if os.path.isdir(dir_path) and directory == str(enquiry_id):
            json_files = os.listdir(dir_path)
            for json_file in json_files:
                file_path = os.path.join(dir_path, json_file)
                all_stored_files.append(file_path)

    # Load 'proposal'
    proposal_directories = os.listdir(proposal_path)
    for directory in proposal_directories:
        dir_path = os.path.join(proposal_path, directory)
        if os.path.isdir(dir_path) and directory == str(enquiry_id):
            json_files = os.listdir(dir_path)
            for json_file in json_files:
                file_path = os.path.join(dir_path, json_file)
                all_proposal_files.append(file_path)

    # Load data for stored_data
    for file_path in all_stored_files:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                try:
                    data = json.load(file)
                    if isinstance(data, dict) and 'enquiry_id' in data:
                        if str(data['enquiry_id']) == str(enquiry_id):
                            stored_data[os.path.basename(file_path)].append(data)
                except json.JSONDecodeError:
                    stored_data[os.path.basename(file_path)].append({'error': 'Invalid JSON file'})

    # Load data for proposal_data
    for file_path in all_proposal_files:
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                try:
                    data = json.load(file)
                    if isinstance(data, dict) and 'enquiry_id' in data:
                        if str(data['enquiry_id']) == str(enquiry_id):
                            proposal_data[os.path.basename(file_path)].append(data)
                except json.JSONDecodeError:
                    proposal_data[os.path.basename(file_path)].append({'error': 'Invalid JSON file'})

    if request.method == 'POST':
        selected_quotation_no = request.POST.get('quotation_selection')
        if not selected_quotation_no:
            return render(request, 'xp/confirm_order.html', {
                'enquiry': enquiry,
                'quotations': quotations,
                'hidrec':hidrec,
                'stored_data': dict(stored_data),
                'proposal_data': dict(proposal_data),
                'confirmed_quotations': confirmed_quotations,
                'error': 'Please select at least one quotation.'
            })

        # Create a new confirmed entry for the same enquiry with the selected quotation
        confirmed_entry = confirmed_enquiry.objects.create(
            created_by=request.user,
            enquiry=enquiry,
            quotation=selected_quotation_no
        )
        confirmed_entry.save()

        enquiry.is_confirmed = True
        enquiry.is_reverted = False  # Optional: Ensure it’s not reverted
        enquiry.save()

        return redirect('confirmedorderss')

    return render(request, 'xp/confirm_order.html', {
        'enquiry': enquiry,
        'quotations': quotations,
        'hidrec':hidrec,
        'stored_data': dict(stored_data),
        'proposal_data': dict(proposal_data),
        'confirmed_quotations': confirmed_quotations
    })



def confirmed_orders(request):
    current_user = request.user
    selected_user_id = request.GET.get('user')
    selected_user = None

    if selected_user_id:
        selected_user = User.objects.filter(id=selected_user_id).first()

    # Retrieve confirmed enquiries based on user type
    if  current_user.is_staff or current_user.is_superuser:
        confirmed_orders = Enquiry.objects.filter(is_confirmed=True).prefetch_related('confirmed_enquiry_set')
    else:
        confirmed_orders = Enquiry.objects.filter(is_confirmed=True, created_by=current_user).prefetch_related('confirmed_enquiry_set')

    # Handle search
    search_query = request.GET.get('search', '')
    if search_query:
        global_filter = Q()

        # Correct the searchable fields
        searchable_fields = [
            'companyname',
            'customername',
            'id',
            'contact',
            'closuredate',  # Replace project_closing_date with closuredate
            'executive__name',
        ]

        for field in searchable_fields:
            global_filter |= Q(**{f"{field}__icontains": search_query})

        confirmed_orders = confirmed_orders.filter(global_filter)

    confirmed_orders = confirmed_orders.distinct()
    

    # Handle toggling of `is_reverted` status when confirming or reverting an order
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

    # Handle pushing the same enquiry with a different quotation number
    if 'push' in request.GET:
        enquiry_id = request.GET.get('push')
        new_quotation_number = request.GET.get('quotation_number')

        enquiry = Enquiry.objects.filter(id=enquiry_id).first()

        if enquiry:
            if enquiry.quotation != new_quotation_number:
                enquiry.quotation = new_quotation_number
                enquiry.is_reverted = False
                enquiry.save()

            return redirect('confirmedorderss')

    return render(request, 'xp/confirmed_orders.html', {
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
        return redirect('confirmedorderss')  # Redirect back if no confirmed order found

    # Access the related Enquiry object via the ForeignKey
    enquiry = confirmed_order.enquiry  # Access the related Enquiry object

    # Get the reason for moving the order to Lost Orders
    reason = request.POST.get("reason", "").strip()

    if not reason:
        messages.error(request, "Please provide a reason for moving the order to Lost Orders.")
        return redirect('confirmedorderss')  # Redirect back if no reason is provided

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
        elif quotation_no.startswith("HIDREC-WASH"):
            quotation_type = "Hidrec_Wash"
        else:
            quotation_type = "unknown"

        if not confirmed_quotations.exists():
            return render(request, 'xp/confirmed_view.html', {
                'error': f"No confirmed enquiry found for enquiry ID {enquiry_id}",
            })

        order = confirmed_quotations.filter(quotation=quotation_no).first()
        if not order:
            return render(request, 'xp/confirmed_view.html', {
                'error': f"No confirmed enquiry found with quotation number {quotation_no} for enquiry ID {enquiry_id}",
            })

        followups = ConfirmedOrderFollowUp.objects.filter(confirmed_order=order)

    except confirmed_enquiry.DoesNotExist:
        return render(request, 'xp/confirmed_view.html', {
            'error': f"No confirmed enquiry found for enquiry ID {enquiry_id}",
        })

    enquiry = order.enquiry

    # Pass enquiry object (with valid ID) to the template
    return render(request, 'xp/confirmed_view.html', {
        'order': order,
        'enquiry': enquiry,                  # Pass the 'enquiry' object here
        'quotations': confirmed_quotations,  # All confirmed enquiries
        'followups': followups,
        'enquiry_id': enquiry_id,            # Ensure this is set correctly
        'quotation_number': quotation_no,
        'quotation_type': quotation_type,
    })


from django.shortcuts import render, get_object_or_404, redirect
from .models import ConfirmedOrderFollowUp, confirmed_enquiry

def add_confirmed_order_followup(request, enquiry_id, quotation_no):
    # Fetch the confirmed order based on enquiry_id and quotation_no
    try:
        order = confirmed_enquiry.objects.get(enquiry_id=enquiry_id, quotation=quotation_no)
    except confirmed_enquiry.DoesNotExist:
        return render(request, 'xp/confirmed_view.html', {
            'error': f"No confirmed order found for enquiry ID {enquiry_id} and quotation {quotation_no}",
        })
    except confirmed_enquiry.MultipleObjectsReturned:
        return render(request, 'xp/confirmed_view.html', {
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
        return redirect('confirmed_view',quotation_no=quotation_no)

    # Get all follow-ups for the current confirmed order
    followups = ConfirmedOrderFollowUp.objects.filter(confirmed_order=order)

    # Render the template with the confirmed order and its follow-ups
    return render(request, 'xp/confirmed_view.html', {
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
    
    # Get the selected user from the dropdown, default to logged-in user if no selection is made
    selected_user_id = request.POST.get('user') if request.method == 'POST' else request.GET.get('user', request.user.id)
    
    try:
        selected_user = User.objects.get(id=selected_user_id)
    except User.DoesNotExist:
        selected_user = request.user  # Default to logged-in user if the selected user doesn't exist
    
    userprofile = UserProfile.objects.filter(user=selected_user).first()
    target = userprofile.target if userprofile else None
    
    if not request.user.is_authenticated:
        return redirect('login')

    total_target = Target.objects.filter(userprofile=userprofile).first()

    total_enquiries = Enquiry.objects.filter(created_by=selected_user).count()
    lost_enquiries = Enquiry.objects.filter(created_by=selected_user, status='lost').count()
    active_enquiries = Enquiry.objects.filter(created_by=selected_user, status='active').count()
    confirmed_orders = ConfirmedOrder.objects.filter(created_by=selected_user).count()
    lost_orders = Enquiry.objects.filter(created_by=selected_user, is_lost=True).count()
    total_quotes = quotation.objects.filter(created_by=selected_user).count()

    total_revenue = quotation.objects.filter(created_by=selected_user).aggregate(total_revenue=Sum('finalamount'))['total_revenue'] or 0
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
        Enquiry.objects.filter(created_by=selected_user)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    labels = [data['month'].strftime('%B') for data in monthly_data]
    data = [data['count'] for data in monthly_data]

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
        'followups': followups
    }

    return render(request, 'xp/dashboard.html', context)




from datetime import datetime
from django.shortcuts import render
from .models import quotation, Enquiry,Xpredict,BankDetails,CommercialQuote,QuotationItem

from django.core.serializers import serialize



from django.db.models import Max


def create_commercial_quote(request, enquiry_id):
    # Fetch the bank details and other necessary data
    banks = BankDetails.objects.all()
    xpredict_data = Xpredict.objects.first()
    products = Products.objects.all()
    enquiry = Enquiry.objects.get(id=enquiry_id)

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
            return render(request, 'xp/commercial_quote.html', {
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
            return render(request, 'xp/commercial_quote.html', {
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
        print("prod :",products_selected)
        print("hsn_codes :",hsn_codes)
        print("🔹 Initial Product selected:", products_selected)
        product_ids = []  # List to store product IDs instead of names

        for i, product_name in enumerate(products_selected):
            product_name = product_name.strip()
            hsncode = hsn_codes[i].strip() if i < len(hsn_codes) else ""
            base_amount = base_amounts[i] if i < len(base_amounts) else 0
            gst = (
                float(cgsts[i]) + float(sgsts[i]) + float(igsts[i])
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

            # Append the product ID
            product_ids.append(str(product.id))

        print("🔹 Updated Product ID List:", product_ids)


     
        # Ensure that the primary lists have equal length
        if not (len(product_ids) == len(hsn_codes) == len(base_amounts) == len(quantities) == len(margins) == len(final_amounts)):
            raise ValueError("Mismatch in the number of products and other item details")

        # Handle missing CGST/SGST/IGST values
        if not cgsts:
            cgsts = ['0'] * len(product_ids)
        if not sgsts:
            sgsts = ['0'] * len(product_ids)
        if not igsts:
            igsts = ['0'] * len(product_ids)

        # Loop through the selected items and create QuotationItem for each one
        for i in range(len(product_ids)):
            print("length :",len(product_ids))
            try:
                product = Products.objects.get(id=product_ids[i])
                hsn_code = hsn_codes[i]
                base_amount = float(base_amounts[i])
                quantity = int(quantities[i])
                margin = float(margins[i])
                final_amount = float(final_amounts[i])

                # Ensure rate is calculated correctly
                rate = (base_amount * quantity) * (1 + margin / 100)

                # Get the GST values for the current product
                cgst = float(cgsts[i]) if cgsts[i] else 0.0
                sgst = float(sgsts[i]) if sgsts[i] else 0.0
                igst = float(igsts[i]) if igsts[i] else 0.0

                # Ensure only one set of GST (CGST + SGST or IGST) is non-zero
                if cgst > 0 and sgst > 0 and igst > 0:
                    raise ValueError(f"Invalid GST values for product at index {i}: Only one of CGST/SGST or IGST should be non-zero.")
                
                if cgst > 0 and sgst > 0:
                    # CGST and SGST for intra-state (valid combination)
                    if igst > 0:
                        raise ValueError(f"Invalid GST values for product at index {i}: IGST should be 0 for intra-state.")
                elif igst > 0:
                    # IGST for inter-state (valid combination)
                    if cgst > 0 or sgst > 0:
                        raise ValueError(f"Invalid GST values for product at index {i}: CGST and SGST should be 0 for inter-state.")
                else:
                    raise ValueError(f"Invalid GST values for product at index {i}: Either CGST and SGST or IGST must be non-zero.")

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
                )
                quotation_item.save()

            except IndexError as e:
                print(f"Index error at {i}: {e}")
                continue  # Continue with the next iteration if an index error occurs
            except Exception as e:
                print(f"Error saving quotation item at index {i}: {e}")
                continue


        return redirect('managequotationpage', enquiry_id=enquiry_id)  # Redirect after saving the quote

    else:
        form = EnquiryForm(instance=enquiry)

    # Pass the data to the template
    bank_data = serialize('json', banks)

    return render(request, 'xp/commercial_quote.html', {
        'enquiry_id': enquiry_id,
        'quotation_no': quotation_no,
        'enquiry': enquiry,
        'form': form,
        'products': products,
        'xpredict': xpredict_data,
        'banks': banks,  # Pass the bank objects to the template
        'bank_data': bank_data,  # Pass serialized bank data to JS
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
                        float(cgsts[i]) + float(sgsts[i]) + float(igsts[i])
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

                    # Append the product ID
                    product_ids.append(str(product.id))

                print("🔹 Updated Product ID List:", product_ids)




                if product_ids:
                    num_items = min(len(products_selected), len(hsn_codes), len(base_amounts),
                                    len(quantities), len(margins), len(cgsts), len(sgsts), len(igsts), len(final_amounts))
                    
                    for i in range(num_items):
                        product_id = product_ids[i]
                        try:
                            product = Products.objects.get(id=product_id)
                        except Products.DoesNotExist:
                            print(f"⚠️ Skipping invalid product ID: {product_id}")
                            continue
                        
                        QuotationItem.objects.create(
                            quotation_no=new_commercial_quote.quotation_no,
                            product=product,
                            hsncode=hsn_codes[i] if i < len(hsn_codes) else '',
                            base_amount=float(base_amounts[i]) if i < len(base_amounts) and base_amounts[i] else 0,
                            quantity=int(quantities[i]) if i < len(quantities) and quantities[i] else 0,
                            margin=float(margins[i]) if i < len(margins) and margins[i] else 0,
                            rate=float(rates[i]) if i < len(rates) and rates[i] else 0,  # ✅ Added rate field
                            cgst=float(cgsts[i]) if i < len(cgsts) and cgsts[i] else 0.0,
                            sgst=float(sgsts[i]) if i < len(sgsts) and sgsts[i] else 0.0,
                            igst=float(igsts[i]) if i < len(igsts) and igsts[i] else 0.0,
                            final_amount=float(final_amounts[i]) if i < len(final_amounts) and final_amounts[i] else 0,
                        )
                        print(f"✅ Quotation Item Saved: {product}")

                print(f"Products: {products_selected}")
                print(f"Rates: {rates}")
                print("🎯 All quotation items processed successfully!")
                return redirect('managequotationpage', enquiry_id=commercial_quote.enquiry_id)

        except Exception as e:
            print(f"❌ Error: {e}")
            context = {
                'commercial_quote': commercial_quote,
                'quotation_items': quotation_items,
                'products': products,
                'xpredict': xpredict_data,
                'banks': banks,
                'new_quotation_no': new_quotation_no,
                'error': str(e)
            }
            return render(request, 'xp/edit_commercial.html', context)
    
    # GET request rendering
    context = {
        'commercial_quote': commercial_quote,
        'quotation_items': quotation_items,
        'products': products,
        'xpredict': xpredict_data,
        'banks': banks,
        'new_quotation_no': new_quotation_no,
    }
    return render(request, 'xp/edit_commercial.html', context)



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

    return render(request, 'xp/quotation_preview.html', context)





def create_techno_commercial_quote(request, enquiry_id):
    # Logic for handling the techno-commercial quote creation
    return render(request, 'xp/techno_commercial_quote.html', {'enquiry_id': enquiry_id,})

from django.http import Http404

def amc_preview(request, quotation_no):
    company = companydetails.objects.all()
    current_date = datetime.now().strftime('%d %b, %Y')

    # Path to the stored_data directory
    base_dir = settings.BASE_DIR
    stored_data_dir = os.path.join(base_dir, 'stored_data')
    
    # Path to the draft_data directory (similar to stored_data)
    draft_data_dir = os.path.join(base_dir, 'AMC_draft')  # Assuming AMC_draft is the directory for draft data

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

    # If no matching file is found in both stored_data and draft_data, raise a 404
    if not found_data and not draft_data:
        raise Http404(f"Quotation with number {quotation_no} not found.")

    # Merge data from stored and draft if both exist (optional, depending on business logic)
    combined_data = found_data if found_data else draft_data

    # Safely fetch the value of 'value' inside 'Grand_Total'
    grand_total = combined_data.get('Grand_Total')
    if grand_total:
        gtotal_value = grand_total[0].get('value')
    else:
        gtotal_value = None
    
    if gtotal_value is not None:
        # Convert to float and convert to words
        g_total_in_words = num2words(float(gtotal_value), lang='en_IN').replace(" and", "").replace(",", "").upper() + " RUPEES ONLY"
    else:
        g_total_in_words = "NONE"

    return render(request, 'xp/amc_preview.html', {
        'quotation_no': quotation_no,
        'data': combined_data,
        'current_date': current_date,
        'company': company,
        'g_total_in_words': g_total_in_words,
        "MEDIA_URL": settings.MEDIA_URL,
    })


    





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
    return render(request, 'xp/preview.html', {'data': data})

from datetime import datetime
import os
import json

def get_quotation_number():
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
    quotation_number = f"EL-HID-AMCPR-{current_year_month}{sequential_part}"

    # Save the updated year-month and sequential number to the file
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
        return render(request, 'xp/error_page.html', {'error': 'Enquiry not found'})
    # Filter QuotationProduct by enquiry
    products = QuotationProduct.objects.get(id=product_id)
    print(products)
    # Generate a quotation number
    quotation_number = get_quotation_number()

    # Filter ParticularsTable by products
    particulars = ParticularsTable.objects.filter(pd_name=products)
    all_headers_particulars = {
        field.name: field.verbose_name.title() for field in ParticularsTable._meta.fields
    }
    excluded_fields_particulars = ['id', 'sl_no']  # Exclude fields
    headers = [
        header for field, header in all_headers_particulars.items()
        if field not in excluded_fields_particulars
    ]

    # Filter OutputTable by enquiry
    outputs = OutputTable.objects.filter(pd_name=products)

    # Filter Contents by a specific product name (e.g., EC1000)
    contents = Contents.objects.filter(pd_name=products)

    # Filter AMC_Pricing by the enquiry
    amc_pricings = AMC_Pricing.objects.filter(pd_name=products)

    # Get the first AMC Pricing for terms
    amc = amc_pricings.first()
    terms = amc.terms_conditions if amc else ''
    terms_and_conds = terms.split(".")

    # Filter InstallationTable by enquiry
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

    # Get the first inclusion record
    inclusion = Inclusions.objects.filter(pd_name=products).first()

    # Retrieve and split maintenance fields
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

    return render(request, 'xp/amc_quotation_details.html', context)



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

        return render(request, "xp/amc_saved.html", {"quotations": quotations})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

# -------------------------------------------edit quotation -----------------------
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
import os
import json


@csrf_exempt
def edit_quotation(request, enquiry_id, quotation_number):
    logger.info("Editing Quotation: %s, %s", enquiry_id, quotation_number)

    # Define the file path for the existing quotation data (JSON file)
    file_path = os.path.join(settings.BASE_DIR, "stored_data", str(enquiry_id), f"{quotation_number}.json")
    print(f"path:",file_path)
    # Check if the file exists
    if not os.path.exists(file_path):
        return JsonResponse({"status": "error", "message": "Quotation not found"}, status=404)

    # Load the existing quotation data from the file
    with open(file_path, "r") as json_file:
        quotation_data = json.load(json_file)
    if request.method == "POST":
        # Initialize lists to hold form data
        data = request.POST
        print(f"sent from template",data)
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
                
            base_dir = os.path.join(settings.BASE_DIR, "stored_data", str(enquiry_id))
            os.makedirs(base_dir, exist_ok=True)
            existing_files = os.listdir(base_dir)
            # Extract version numbers for files matching the quotation_number
            version_numbers = [
                int(f.split("R")[-1].split(".")[0])  # Extract the version number
                for f in existing_files
                if f.startswith(quotation_number) and f.endswith(".json") and "R" in f.split(".")[0][-3:]
            ]
            # Calculate the next version
            latest_version = max(version_numbers, default=0)
            new_version = latest_version + 1
                
            # Construct the new file name
            quotation = f"{quotation_number}R{new_version}"
            print(f"before appending",quotation)
            new_file_name = f"{quotation}.json"
            print(new_file_name)
            new_file_path = os.path.join(base_dir, new_file_name)
            print(f"new path",new_file_path)
            # Save the edited data to the new versioned file
            
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
                    'quotation_number':quotation,
                }
            edited_data = final_data
            with open(new_file_path, "w") as json_file:
                json.dump(edited_data, json_file, indent=4)
            return JsonResponse({"message": "Quotation updated successfully", "file": new_file_name})    
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    # Return the template with the existing data for editing
    data_json = json.dumps(quotation_data)
    return render(request, 'xp/edit_quotation.html', {'quotation_data': quotation_data, 'data': data_json})




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
    
#     return render(request, 'xp/amc_edit.html', {
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
        return render(request, 'xp/error_page.html', {'error': 'Enquiry not found'})
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
    return render(request, 'xp/proposal_details.html', context)




def product_list(request, enquiry_id):
    try:
        enquiry = Enquiry.objects.get(id=enquiry_id)
    except Enquiry.DoesNotExist:
        return render(request, 'xp/error_page.html', {'error': 'Enquiry not found'})

    # Fetch all products related to the enquiry
    products = QuotationProduct.objects.all()
    # Handle form submission
    if request.method == 'POST':
        selected_product_id = request.POST.get('selected_product')
        if selected_product_id:
            # Redirect to the amc_quotation_details view with the enquiry ID
            return redirect('amc_quotation_details', enquiry_id=enquiry_id,product_id=selected_product_id)

    return render(request, 'xp/product_list.html', {'products': products, 'enquiry_id': enquiry_id})


from django.core.files.storage import default_storage

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

        # Define base directory for the enquiry_id
        base_dir = os.path.join(settings.BASE_DIR, "proposal", str(enquiry_id))
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



def proposal_preview(request, quotation_no):
    # Fetch company details
    company = companydetails.objects.all()
    
    # Get the current date
    current_date = datetime.now().strftime('%d %b, %Y')

    # Correct the path to the directory where JSON files are stored
    stored_data_dir = os.path.join(settings.BASE_DIR, 'proposal')
    proposal_stored_data_dir = os.path.join(settings.BASE_DIR, 'proposal_draft')

    found_data = None

    # Traverse all directories in 'proposal' directory
    for directory in os.listdir(stored_data_dir):
        dir_path = os.path.join(stored_data_dir, directory)

        if os.path.isdir(dir_path):  # Ensure it's a directory
            # Look for a file matching the quotation_no
            file_path = os.path.join(dir_path, f"{quotation_no}.json")

            if os.path.exists(file_path):  # Check if the file exists
                # Load the JSON data
                try:
                    with open(file_path, 'r') as file:
                        found_data = json.load(file)
                except json.JSONDecodeError:
                    raise Http404(f"Invalid JSON file: {file_path}")
                break  # Stop searching once file is found

    # Traverse all directories in 'proposal' directory
    for directory in os.listdir(proposal_stored_data_dir):
        dir_path = os.path.join(proposal_stored_data_dir, directory)

        if os.path.isdir(dir_path):  # Ensure it's a directory
            # Look for a file matching the quotation_no
            file_path = os.path.join(dir_path, f"{quotation_no}.json")

            if os.path.exists(file_path):  # Check if the file exists
                # Load the JSON data
                try:
                    with open(file_path, 'r') as file:
                        found_data = json.load(file)
                except json.JSONDecodeError:
                    raise Http404(f"Invalid JSON file: {file_path}")
                break  # Stop searching once file is found

    # If no matching file is found, raise a 404 error
    if not found_data:
        raise Http404(f"Quotation with number {quotation_no} not found.")
    for key, value in found_data.items():
        print(f" {key}: {value}")    # Pass the data to the template
    return render(request, 'xp/proposal_preview.html', {
        'quotation_no': quotation_no,
        'data': found_data,
        'current_date': current_date,
        'company': company,
    })


#########################################
import csv
from django.http import HttpResponse
from .models import Enquiry


def product_pr(request, enquiry_id):
    try:
        enquiry = Enquiry.objects.get(id=enquiry_id)
    except Enquiry.DoesNotExist:
        return render(request, 'xp/error_page.html', {'error': 'Enquiry not found'})

    # Fetch all products related to the enquiry
    products = QuotationProduct.objects.all()
    # Handle form submission
    if request.method == 'POST':
        selected_product_id = request.POST.get('selected_product')
        if selected_product_id:
            # Redirect to the amc_quotation_details view with the enquiry ID
            return redirect('proposal_details', enquiry_id=enquiry_id,product_id=selected_product_id)

    return render(request, 'xp/product_list_pr.html', {'products': products, 'enquiry_id': enquiry_id})



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
            # Extract version numbers for files matching the quotation_number
            version_numbers = [
                int(f.split("R")[-1].split(".")[0])  # Extract the version number
                for f in existing_files
                if f.startswith(quotation_number) and f.endswith(".json") and "R" in f.split(".")[0][-3:]
            ]
            # Calculate the next version
            latest_version = max(version_numbers, default=0)
            new_version = latest_version + 1
                    
            # Construct the new file name
            quotation = f"{quotation_number}R{new_version}"
            print(f"before appending",quotation)
            new_file_name = f"{quotation}.json"
            print(new_file_name)
            new_file_path = os.path.join(base_dir, new_file_name)
            print(f"new path",new_file_path)
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
    return render(request, 'xp/proposal_edit.html', {'proposal_data': proposal_data, 'data': data_json})



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
    return render(request, 'xp/draft_edit_quotation.html', {
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
    return render(request, 'xp/draft_proposal_edit.html', {'proposal_data': proposal_data, 'data': data_json})


from .views import RevertRemark
from reportlab.lib.pagesizes import letter
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
    html = render_to_string('xp/confirmed_orders_pdf_template.html', {'confirmed_orders': page_obj.object_list})

    # Create a PDF response using xhtml2pdf
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="confirmed_orders.pdf"'

    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)

    return response







def hidrec_wash(request, enquiry_id):
    hid = Hidrec_wash.objects.all()

    if request.method == "POST":
        # Generate quotation number in format HIDREC-WASH-YYMM001
        current_date = now()
        yy_mm = current_date.strftime("%y%m")  # Extract YYMM from current date
        last_entry = ConfirmedHidrecWash.objects.filter(quotation_no__startswith=f"HIDREC-WASH-{yy_mm}").order_by('-quotation_no').first()
        
        if last_entry and last_entry.quotation_no:
            last_number = int(last_entry.quotation_no[-3:])  # Extract last 3 digits
            new_number = last_number + 1
        else:
            new_number = 1  # Start from 001 if no entries exist for the month

        quotation_no = f"HIDREC-WASH-{yy_mm}{new_number:03d}"  # Format as HIDREC-WASH-YYMMXXX
        
        # Create a new confirmed record
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
        return redirect('managequotationpage',enquiry_id=enquiry_id)  # Redirect to a success page or the same form page
    
    return render(request, 'xp/hidrec_wash.html', {'enquiry_id': enquiry_id, 'hid': hid})




def hidrecwash_preview(request,quotation_no):
    hidrec=ConfirmedHidrecWash.objects.filter(quotation_no=quotation_no)
    company = companydetails.objects.all()
    current_date = datetime.now().strftime('%d %b, %Y')


    return render(request,'xp/hidrecwash_preview.html',{'hidrec':hidrec,'company':company,'current_date':current_date})


import re
from django.shortcuts import render, redirect
from .models import ConfirmedHidrecWash

def edit_hidrecwash(request, quotation_no, enquiry_id):
    # Get all existing records for the given quotation_no
    hidrec = ConfirmedHidrecWash.objects.filter(quotation_no=quotation_no)

    if request.method == 'POST':
        # Find the latest entry that starts with the same base quotation number
        latest_entry = ConfirmedHidrecWash.objects.filter(
            quotation_no__startswith=quotation_no
        ).order_by('-quotation_no').first()

        # Default revision number
        rev_num = 1  

        if latest_entry:
            # Use regex to extract the revision number at the end (e.g., R1, R2)
            match = re.search(r'R(\d+)$', latest_entry.quotation_no)
            if match:
                rev_num = int(match.group(1)) + 1  # Extract and increment revision number

        # Create new quotation number with revision
        new_quotation_no = f"{quotation_no}R{rev_num}"

        # Duplicate and save new records
        for record in hidrec:
            record.pk = None  # Reset primary key to create a new entry
            record.quotation_no = new_quotation_no  # Assign new revision number
            record.save()  # Save as new record

        # Redirect to the newly created revision
        return redirect('managequotationpage', enquiry_id=enquiry_id)

    return render(request, 'xp/edit_hidrecwash.html', {'quotation_no': quotation_no, 'enquiry_id': enquiry_id, 'hidrec': hidrec})
