from datetime import date, datetime
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from django.contrib.auth.models import User
from website.models import Expense, AdvanceGroup, AdvanceAssignment
from decimal import Decimal
from django.db import models

def dashboard_data(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    selected_user_id = request.GET.get('user_id')

    # Default to the current month if no filters are provided
    if not from_date or not to_date:
        today = date.today()
        from_date = today.replace(day=1)
        to_date = today
    else:
        try:
            from_date = datetime.strptime(from_date, "%Y-%m-%d").date()
            to_date = datetime.strptime(to_date, "%Y-%m-%d").date()
        except ValueError:
            today = date.today()
            from_date = today.replace(day=1)
            to_date = today

    # Base filtering parameters
    filter_kwargs = {
        'transaction_date__range': (from_date, to_date),
        'is_draft': False
    }
    adv_filter_kwargs = {
        'created_at__date__range': (from_date, to_date)
    }

    # Handle User Filtering (Staff vs User)
    users = None
    if user.is_staff or user.is_superuser:
        users = User.objects.filter(is_active=True).order_by('first_name')
        if selected_user_id:
            try:
                target_user = User.objects.get(id=selected_user_id)
                filter_kwargs['created_by'] = target_user
                assigned_group_ids = AdvanceAssignment.objects.filter(user=target_user).values_list('group_id', flat=True)
                advance_groups = AdvanceGroup.objects.filter(id__in=assigned_group_ids, **adv_filter_kwargs)
            except (User.DoesNotExist, ValueError):
                advance_groups = AdvanceGroup.objects.filter(**adv_filter_kwargs)
        else:
            advance_groups = AdvanceGroup.objects.filter(**adv_filter_kwargs)
    else:
        filter_kwargs['created_by'] = user
        assigned_group_ids = AdvanceAssignment.objects.filter(user=user).values_list('group_id', flat=True)
        advance_groups = AdvanceGroup.objects.filter(id__in=assigned_group_ids, **adv_filter_kwargs)

    expenses = Expense.objects.filter(**filter_kwargs)

    # Calculate Core Metrics (Expenses)
    total_claimed = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
    approved_amount = expenses.filter(is_approved=True, is_rejected=False).aggregate(Sum('amount'))['amount__sum'] or 0
    pending_amount = expenses.filter(is_approved=False, is_rejected=False).aggregate(Sum('amount'))['amount__sum'] or 0
    rejected_amount = expenses.filter(is_rejected=True).aggregate(Sum('amount'))['amount__sum'] or 0
    paid_amount = expenses.filter(status='paid').aggregate(Sum('amount'))['amount__sum'] or 0

    # Calculate Advance Metrics
    total_advance_assigned = advance_groups.aggregate(Sum('total_advance'))['total_advance__sum'] or 0
    total_advance_used = advance_groups.aggregate(Sum('used_advance'))['used_advance__sum'] or 0
    
    adv_metrics = advance_groups.aggregate(
        remaining=Sum('remaining_balance', filter=Q(remaining_balance__gt=0)),
        overdue=Sum('remaining_balance', filter=Q(remaining_balance__lt=0))
    )
    total_advance_remaining = adv_metrics['remaining'] or 0
    total_advance_overdue = abs(adv_metrics['overdue'] or 0)

    # Trend Chart (Month-wise) using transaction_date
    trends = expenses.annotate(month=TruncMonth('transaction_date')).values('month').annotate(
        claimed=Sum('amount'),
        paid=Sum('amount', filter=Q(status='paid'))
    ).order_by('month')

    months_list = [t['month'].strftime('%b %Y') for t in trends]
    claimed_amounts = [float(t['claimed'] or 0) for t in trends]
    paid_amounts = [float(t['paid'] or 0) for t in trends]

    # Item Type Statistics
    item_types_qs = expenses.values('item_type').annotate(
        count=models.Count('id'),
        total_amount=Sum('amount')
    )
    
    item_type_data = {
        'fright_transportation': {'count': 0, 'total_amount': 0},
        'fuel_oil': {'count': 0, 'total_amount': 0},
        'food_grocery': {'count': 0, 'total_amount': 0},
        'others': {'count': 0, 'total_amount': 0},
        'vendor': {'count': 0, 'total_amount': 0},
        'reimbursement': {'count': 0, 'total_amount': 0},
        'site_services': {'count': 0, 'total_amount': 0},
        'advances': {'count': 0, 'total_amount': 0},
        'travelling': {'count': 0, 'total_amount': 0},
        'electricity_bill': {'count': 0, 'total_amount': 0},
        'internet_bill': {'count': 0, 'total_amount': 0},
        'postage_telegram': {'count': 0, 'total_amount': 0},
        'machine_repair': {'count': 0, 'total_amount': 0},
        'conveyance': {'count': 0, 'total_amount': 0},
        'stationary_printing': {'count': 0, 'total_amount': 0},
        'hospitality': {'count': 0, 'total_amount': 0},
    }

    for entry in item_types_qs:
        itype = entry['item_type']
        if itype in item_type_data:
            item_type_data[itype] = {
                'count': entry['count'],
                'total_amount': float(entry['total_amount'] or 0)
            }

    return {
        'dashboard_data': {
            'from_date': from_date,
            'to_date': to_date,
            'total_claimed': total_claimed,
            'approved_amount': approved_amount,
            'pending_amount': pending_amount,
            'rejected_amount': rejected_amount,
            'paid_amount': paid_amount,
            'total_advance_assigned': total_advance_assigned,
            'total_advance_used': total_advance_used,
            'total_advance_remaining': total_advance_remaining,
            'total_advance_overdue': total_advance_overdue,
            'months_list': months_list,
            'claimed_amounts': claimed_amounts,
            'paid_amounts': paid_amounts,
            'item_type_data': item_type_data,
            'selected_user_id': selected_user_id,
            'users': users,
        }
    }


from django.shortcuts import get_object_or_404
from .models import Notification, User, CashVoucher, Expense
from datetime import datetime

def pay_now_context(request):
    payment_details = None
    selected_user = None
    expenses = None
    total_amount_to_be_paid = None
    transaction_id = None
    from_date = None
    to_date = None
    selected_filter = None

    # If 'user_id' is provided in the request
    user_id = request.GET.get('user_id', None)
    if user_id:
        selected_user = get_object_or_404(User, id=user_id)
        expenses = Expense.objects.filter(created_by=selected_user, status="pending")
        total_amount_to_be_paid = request.GET.get('total_amount_to_be_paid')
        from_date = request.GET.get('from_date')
        to_date = request.GET.get('to_date')
        selected_filter = request.GET.get('selected_filter')

        # Logic to generate transaction ID (XPTR+YY+M+counter)
        current_year = str(datetime.now().year)[2:]
        current_month = str(datetime.now().month).zfill(2)  # Ensure month is two digits
        counter = CashVoucher.objects.filter(created_by=selected_user).count() + 1  # Add 1 to the count
        counter_formatted = f"{counter:04d}"  # Zero-pad the counter to 4 digits
        transaction_id = f"XPTR{current_year}{current_month}{counter_formatted}"

    # If the form is submitted
    if request.method == 'POST':
        # Get form data
        transaction_id = request.POST.get('transaction_id')
        amount = request.POST.get('amount')
        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')
        screenshot = request.FILES.get('screenshot')

        # Prepare payment details
        payment_details = {
            'transaction_id': transaction_id,
            'amount': amount,
            'from_date': from_date,
            'to_date': to_date,
            'screenshot': screenshot,
        }

    return {
        'selected_user': selected_user,
        'expenses': expenses,
        'total_amount_to_be_paid': total_amount_to_be_paid,
        'transaction_id': transaction_id,
        'from_date': from_date,
        'to_date': to_date,
        'selected_filter': selected_filter,
        'payment_details': payment_details,
    }

from .models import CashVoucher
from datetime import datetime

def generate_voucher_number(request):
    # Get the current date
    current_date = datetime.now()
    
    # Format the year as 'yy' and month as 'mm'
    year_month = current_date.strftime('%y%m')  # 'yy' format for year and 'mm' for month
    
    # Define the voucher counter. In practice, this would come from your database, and you would
    # increment the counter for each new voucher in the same month.
    # For demonstration purposes, we are assuming the counter starts at 1.
    last_voucher = CashVoucher.objects.filter(voucher_number__startswith=f"XPCV{year_month}").order_by('voucher_number').last()

    if last_voucher:
        # Extract the number part from the last voucher and increment it
        last_number = int(last_voucher.voucher_number[-4:])
        next_number = last_number + 1
    else:
        # If no voucher exists for this month, start from 1
        next_number = 1


    counter_str = str(next_number).zfill(4)

    # Combine everything into the final voucher number
    voucher_number = f"XPCV{year_month}{counter_str}"
    
    return {'voucher_number': voucher_number}


# website/context_processors.py

# # In context processor
# def user_notifications(request):
#     if request.user.is_authenticated:
#         notifications = Notification.objects.filter(user=request.user, status='unread')
#         return {'user_notifications': notifications}
#     return {'user_notifications': []}

from .models import Notification

def notifications(request):
    # Check if the user is authenticated
    if request.user.is_authenticated:
        if request.user.is_superuser:  # For admin users, get all notifications
            notifications = Notification.objects.all().order_by('-created_at').values('id', 'title', 'message', 'status', 'created_at')
        else:  # For regular users, filter by the current user (if notifications are user-specific)
            notifications = Notification.objects.filter(user=request.user).order_by('-created_at').values('id', 'title', 'message', 'status', 'created_at')

        # Calculate unread notifications count
        unread_count = notifications.filter(status='unread').count()
    else:
        # If the user is not authenticated, return an empty list and count
        notifications = []
        unread_count = 0

    # Return notifications and unread_count as part of the context
    return {
        'notifications': list(notifications),
        'unread_count': unread_count,
    }