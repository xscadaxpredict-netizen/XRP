from django.urls import path
from . import views 
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from . import views

urlpatterns = [
    # Home
    path('home', views.home, name="home"),

    # File Upload
    path('success/', views.success_view, name='success'),

    # Item Form
    path('item_form/', views.item_form, name='item_form'),


    # Cash Voucher
    path('cash_voucher/', views.cash_voucher, name='cash_voucher'),
    path('create-cash-voucher/', views.create_cash_voucher, name='create_cash_voucher'),
    path('cash_voucher/success/', views.success_view, name='cash_voucher_success'),
    path('approve-voucher/<str:voucher_number>/', views.approve_cash_voucher, name='approve_cash_voucher'),
    path('approved-vouchers/', views.approved_vouchers, name='approved_vouchers'),
    path('rejected-vouchers/', views.rejected_vouchers, name='rejected_vouchers'),
    path('reject/', views.reject_voucher, name='reject_voucher'),
    path('dashboard/', views.vouchers_dashboard, name='vouchers_dashboard'),
    path('payable/', views.payable, name='payable'),
    path('get_users_by_zone/', views.get_users_by_zone, name='get_users_by_zone'),
    
    

    # E-Voucher
    path('e-voucher/', views.e_voucher, name='e_voucher'),
    path('e-vouchers/', views.item_form, name='e_vouchers'),

    

    # Expense Management
    path('expense/form/', views.expense_form, name='expense_form'),
    path('expense/details/<int:expense_id>/', views.expense_details, name='expense_details'),

    path('expense_home/', views.expense_home, name='expense_home'),  # Expense home page

    # New Item and Cash Voucher Forms
    path("new-item-form/<int:user_id>/", views.new_item_form, name="new_item_form"),
    path('new-cash-voucher-form/', views.new_cash_voucher_form, name='new_cash_voucher_form'),  # Renamed for clarity

    # Edit Item and Cash Voucher

    path('edit-cash-voucher/<int:voucher_id>/', views.edit_cash_voucher_form, name='edit_cash_voucher_form'),

    # Voucher Data
    path('get_voucher_data/', views.get_voucher_data, name='get_voucher_data'),
    path('draft-vouchers/', views.draft_vouchers, name='draft_vouchers'),


    # Search
    path('search/', views.search_view, name='search_view'),

    # Update Item
    path('update_item/', views.update_item, name='update_item'),
    path('voucher-summary/', views.transaction, name='transaction'),

    path('edit/<int:item_id>/', views.edit_item, name='edit_item'),
    path('export/', views.export_vouchers, name='export_vouchers'),
    path('export-cash-vouchers/', views.export_cash_vouchers, name='export_cash_vouchers'),

    path('payable/', views.payable, name='payable'),
    path('payable/add-adjustment/', views.add_adjustment, name='add_payable_adjustment'),
    path('payable/get-user-credit-notes/', views.get_user_credit_notes, name='get_user_credit_notes'),
    path('pay_now/<int:user_id>/', views.pay_now, name='pay_now'),
    path('process_payment/', views.process_payment, name='process_payment'),
    # Add a success page for when the payment is processed
    path('payment_success/', views.payment_success, name='payment_success'),
    path('user-payments/', views.payments, name='payments'),
   
    # path('payment-history/', views.payment_history, name='payment_history'),
    path('export_payments/', views.export_payments, name='export_payments'),
    path('get-monthwise-data/', views.get_monthwise_data, name='get_monthwise_data'),
    

    # path('scan-amount/', views.scan_amount, name='scan_amount'),
    # path('extract_amount/', views.extract_amount, name='extract_amount'),
    #  path('extract-amount-from-bill/', views.extract_amount_from_bill_view, name='extract-amount-from-bill'),


    # path('process-bill-photo/', process_bill_photo, name='process-bill-photo'),
    # path('process-gst-photo/', process_gst_photo, name='process-gst-photo'),
    # path('process-uploaded-image/', views.process_uploaded_image, name='process_uploaded_image'),
    # path('process-photo/', views.process_photo, name='process_photo'),  # Add this line
    path('upload-temporary/', views.upload_temporary, name='upload_temporary'),
    path('get_price_per_km/', views.get_price_per_km, name='get_price_per_km'),
    path('approve-voucher/', views.approve_voucher_ajax, name='approve_voucher_ajax'),

    path('ajax/reject-cash-voucher/', views.reject_cash_voucher_ajax, name='reject_cash_voucher_ajax'),
    path("assign/group-advance/", views.assign_advances, name="assign_advances"),
    path("assigned-groups/", views.view_assigned_groups, name="view_assigned_groups"),
    path("update/balance/<int:group_id>/", views.update_group_balance, name="update_group_balance"),
    path("delete-group/<int:group_id>/", views.delete_group, name="delete_group"),
    path("update-group-members/<int:group_id>/", views.update_group_members, name="update_group_members"),
    path('expenses/approve/<int:expense_id>/', views.approve_expense, name='approve_expense'),
    path('expenses/reject/', views.reject_expense, name='reject_expense'),
    path('approve-tip-voucher/', views.approve_tip_voucher, name='approve_tip_voucher'),
    path('submit-request/', views.submit_request, name='submit_request'),
     path('view-requests/', views.view_requests, name='view_requests'),
    path('chat/<int:req_id>/', views.chat_request, name='chat_request'),
    path('ajax-reply/', views.ajax_reply_request, name='ajax_reply_request'),
    path("ajax/fetch-messages/<int:req_id>/", views.fetch_messages, name="fetch_messages"),
    path('advances/export/excel/', views.export_advances_excel, name='export_advances'),
    path('advances/export/pdf/', views.export_advances_pdf, name='export_advances_pdf'),


    path('expenses/request-delete/<int:expense_id>/', views.request_expense_deletion, name='request_expense_deletion'),
    path('expenses/delete/<int:expense_id>/', views.delete_expense, name='delete_expense'),
    path('delete-request/', views.delete_request, name='delete_request'),
    path("advance-group/<int:group_id>/balance/", views.get_group_balance, name="get_group_balance"),
    path('close_group/<int:group_id>/', views.close_group, name='close_group'),
    
    path("directpay/", views.directpay_form, name="directpay_form"),
    path("directpay/preview/", views.directpay_preview, name="directpay_preview"),
    path("directpay/<int:dp_id>/edit/", views.edit_directpay_form, name="directpay_form_edit"),
    path("directpay/<int:dp_id>/request-delete/", views.directpay_request_delete, name="directpay_request_delete"),
    path("directpay/<int:dp_id>/reject-delete/", views.directpay_reject_delete, name="directpay_reject_delete"),
    path("directpay/<int:dp_id>/delete/", views.directpay_delete, name="directpay_delete"),

    path("payments/update/<int:id>/", views.update_payment, name="update_payment"),
    path("delete-advance-log/<int:log_id>/", views.delete_advance_log, name="delete_advance_log"),

    path("fix-advance-balances/", views.fix_advance_balances, name="fix_advance_balances"),
    path("fix-advance-balances/confirm/", views.confirm_fix_advance_balances, name="confirm_fix_advance_balances"),


    path("api/mobile-session/", views.mobile_session),
    path("mobile-login/", views.mobile_token_login),
    path("api/save-fcm-token/", views.save_fcm_token),


    
    









    # path('mappls_search/', views.mappls_search, name='mappls_search'),
    # path('mappls_place_details/', views.mappls_place_details, name='mappls_place_details'),
    path('toggle-transaction-date-restriction/', views.toggle_transaction_date_restriction, name='toggle_transaction_date_restriction'),
    path('advance-groups-ajax/', views.advance_groups_ajax, name='advance_groups_ajax'),
    path('api/advance-groups-list/', views.api_advance_groups_list, name='api_advance_groups_list'),
    path('api/close-groups-ajax/', views.api_close_groups_ajax, name='api_close_groups_ajax'),
    path('update-holidays/', views.update_holidays, name='update_holidays'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)