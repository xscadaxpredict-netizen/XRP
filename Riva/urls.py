from .import views
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from .views import enquiry_details
from django.contrib.auth.views import LoginView, LogoutView
from django.views.decorators.cache import never_cache
from app.views import CustomLoginView
from . import exportviews

from . import api_views

urlpatterns = [
    path('api/login/', api_views.CustomAuthToken.as_view(), name='api_login'),
    path('api/site-visit-summary/', api_views.SiteVisitAPIView.as_view(), name='api_site_visit_summary'),
    path('api/notifications/', api_views.NotificationAPIView.as_view(), name='api_notifications'),
    path('api/save-fcm-token/', api_views.SaveFCMTokenAPIView.as_view(), name='api_save_fcm_token'),
    
    path('Home', views.Home, name='Home'),
    path('enquiry/', views.enquiry_view, name='newenquirypage'),
    path('potential-duplicates/', views.potential_duplicates, name='potential_duplicates'),
    path('merge-enquiry/<int:duplicate_id>/<int:target_id>/', views.merge_enquiry, name='merge_enquiry'),
    path('api/check-duplicate/', views.check_duplicate_api, name='check_duplicate_api'),
    path('enqhome/', views.enq_home, name='enquries'),
    path('add/', views.add_data, name='add_data'),
    path('enquiry/<int:id>/details/', views.enquiry_details, name='enquiry_details'),
    path('lostorders/', views.lost_orders_view, name='lost_orders'),
    path('enquiry/<int:id>/details/push-to-lost-order/', views.push_to_lost_order, name='push_to_lost_order'),
    path('lost-orders/delete/<int:id>/', views.delete_lost_order, name='deletelostorder'),
    path('enquiry/<int:id>/retrieve/', views.retrieve_lost_order, name='retrievelostorder'),
    path('edit-enquiry/<int:enquiry_id>/', views.edit_enquiry, name='edit-enquiry'),
    path('manage_quotation/<int:enquiry_id>/',views.manage_quotation,name='managequotationpage'),
    path('upload_quote/<int:enquiry_id>/',views.upload_quote,name='upload_quote'),
    # path('new_quotation/<int:enquiry_id>/', views.create_quotation, name='newquotation'),
    path('quotation_details/<int:quotation_id>/', views.quotation_details, name='quotation_details'),
    path('confirm_order/<int:enquiry_id>/', views.confirm_order, name='confirm_order'),
    path('confirmed_orders/', views.confirmed_orders, name='confirmed_orders'),
    path('enquiry/<int:enquiry_id>/add-followup/', views.add_followup, name='add_followup'),
    path('push-to-lost-order/<int:enquiry_id>/<str:quotation_no>/', views.push_to_lost_order_from_confirmed, name='push_to_lost_order_from_confirmed'),
    path('confirmedview/<int:enquiry_id>/<str:quotation_no>/details/', views.confirmed_view, name='confirmed_view'),
    path('confirmed/<int:enquiry_id>/<str:quotation_no>/', views.add_confirmed_order_followup, name='add_confirmed_order_followup'),
    path('', never_cache(CustomLoginView.as_view(template_name='app/login.html')), name='login'), 
    path('login/', never_cache(CustomLoginView.as_view( template_name='app/login.html', redirect_authenticated_user=True, extra_context={'debug': 'login-view-hit'})), name='login'),
    path('logout/', LogoutView.as_view(template_name='app/logout.html'), name='logout'),

    path('create-commercial-quote/<int:enquiry_id>/', views.create_commercial_quote, name='create_commercial_quote'),
    path('create-techno-commercial-quote/<int:enquiry_id>/', views.create_techno_commercial_quote, name='create_techno_commercial_quote'),

    path('quotation/preview/<str:quotation_no>/', views.preview_quotation, name='preview_quotation'),
    path('quote/edit/<str:quotation_no>/', views.Edit_commercial_quote, name='Edit_commercial'),
    path('get_bank_details/<int:bank_id>/', views.get_bank_details, name='get_bank_details'),
    path('dashboard/', views.dashboard, name='crm_dashboard'),
    path('dealership-dashboard/', views.dealership_dashboard, name='dealership_dashboard'),
    path('dealerships-management/', views.manage_dealerships, name='manage_dealerships'),
    path('dealerships-management/edit/<int:dealership_id>/', views.edit_dealership, name='edit_dealership'),
    path('dealerships-management/pricing/<int:dealership_id>/', views.manage_dealership_pricing, name='manage_dealership_pricing'),
    path('dealerships-management/create-user/<int:dealership_id>/', views.create_dealership_user, name='create_dealership_user'),
    #  path('live_search/', views.live_search, name='live_search'),
     

    #############################################################################################################################
    path('amc-quotation-details/<int:enquiry_id>/<int:product_id>/', views.amc_quotation_details, name='amc_quotation_details'),
    path('', views.saved_quotations, name='saved_quotations'),
    path('store/<int:enquiry_id>/<str:quotation_number>/',views.store_data, name="store_data"),
    path('draft/<int:enquiry_id>/<str:quotation_number>/',views.draft_store_data, name="draft_store_data"),

    path('amc/preview/<str:quotation_no>/', views.amc_preview, name='amc_preview'),
    path('edit_quotation/<int:enquiry_id>/<str:quotation_number>/', views.edit_quotation, name='edit_quotation'),
   
    path('product-list/<int:enquiry_id>/', views.product_list, name='product_list'),

    path("saved-quotations/", views.saved_quotations, name="saved_quotations"),
    
    # path('saved-quotations/preview/<str:quotation_number>/', views.preview, name='preview'),
#######################################################################################################################################
    path('proposal/<int:enquiry_id>/<str:product_id>/', views.proposal_details, name='proposal_details'),
    path('proposal/store/<int:enquiry_id>/<str:quotation_number>/', views.proposal_store_data, name='proposal_store_data'),
    path('proposal/preview/<str:quotation_no>/', views.proposal_preview, name='proposal_preview'),
    path('product-pr/<int:enquiry_id>/', views.product_pr, name='product_pr'),
    path('edit_quotation_pr/<int:enquiry_id>/<str:quotation_number>/', views.edit_quotation_pr, name='edit_quotation_pr'),
    path('proposal_draft/<int:enquiry_id>/<str:quotation_number>/',views.proposal_draft_store_data, name="proposal_draft_store_data"),



###############################################################################################################


###########################################################################################################
    path('enquiry/revert/<int:enquiry_id>/', views.revert_to_enquiries, name='revert_to_enquiries'),
##############################################################################################################
    
    path('draft_edit_quotation/<int:enquiry_id>/<str:quotation_number>/', views.draft_edit_quotation, name='draft_edit_quotationpage'),
    path('draft_edit_quotation_pr/<int:enquiry_id>/<str:quotation_number>/', views.draft_edit_quotation_pr, name='draft_edit_quotation_page'),

##################################################################################################################
    path('export/details-enquiries/<int:enquiry_id>/pdf/', views.export_pdf_details, name='export_details_enquiries_pdf'),
    #######################################################################################################################
    path('export/confirmed-enquiries/pdf/', views.export_confirmed_orders_pdf, name='export_confirmed_orders_pdfpage'),



    path('export/confirmed-orders/csv/', exportviews.export_confirmed_orders_csv, name='export_confirmed_orders_csv'),
    path('export/confirmed-orders/xlsx/', exportviews.export_confirmed_orders_xlsx, name='export_confirmed_orders_xlsx'),
    path('export/confirmed-orders/pdf/', exportviews.export_confirmed_orders_pdf, name='export_confirmed_orders_pdf'),





    path('export-lost-enquiries-csv/', exportviews.export_lost_enquiries_csv, name='export_lost_enquiries_csv'),
    path('export-lost-enquiries-xlsx/', exportviews.export_lost_enquiries_xlsx, name='export_lost_enquiries_xlsx'),
    path('export-lost-enquiries-pdf/', exportviews.export_lost_enquiries_pdf, name='export_lost_enquiries_pdf'),



    path('export/enquiries/csv/', exportviews.export_enquiries_csv, name='export_enquiries_csv'),
    path('export/enquiries/pdf/', exportviews.export_enquiries_pdf, name='export_enquiries_pdf'),
    path('export/enquiries/xlsx/', exportviews.export_enquiries_xlsx, name='export_enquiries_xlsx'),
    

############################
    path('export_quotation/<int:enquiry_id>/',exportviews. export_quotation_data, name='export_quotation_data'),
    path('export-pdf/<int:enquiry_id>/', exportviews.export_quotation_pdf, name='export_pdf'),
    path('export-excel/<int:enquiry_id>/', exportviews.export_quotation_excel, name='export_excel'),


    path('create-hidrec-wash/<int:enquiry_id>/', views.hidrec_wash, name='Hidrec_wash'),
    path('hidrec-wash/preview/<str:quotation_no>/', views.hidrecwash_preview, name='wash_preview'),
    path('hid-wash/edit/<str:quotation_no>/<int:enquiry_id>', views.edit_hidrecwash, name='edit_wash'),









    
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
