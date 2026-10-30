from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LoginView, LogoutView
from . import exportviews  # Import the views from exportview.py
from . import views

urlpatterns = [
    # path('', views.base, name='index'),  # Home 
    path('logout/', LogoutView.as_view(template_name='app/logout.html'), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('home/', views.home, name='home'),  # Match to this URL
    path('sucess/',views.success,name='success'),
    # service report 
    path('riva/api/service-reports/', views.service_reports_api, name='api_service_reports'),
    path('servicereport/', views.servicereport, name='servicereport'),  # Match to this URL
    path('service-reports/new/', views.service_report_new, name='service_report_new'),
    path('service-report/<int:pk>/', views.view_service_report, name='view_service_report'),
    path('service-reports/edit/<int:report_id>/', views.edit_service_report, name='service_report_edit'),
    path('service-report/<int:pk>/pdf/', views.service_report_pdf, name='service_report_pdf'),
    path('service-report/<int:report_id>/update-notes/', views.servireport_edithistory, name='servireport_edithistory'),
    path('service-report/update-status/<int:pk>/<str:action>/', views.update_service_report_status, name='update_service_report_status'),

    path('service-report/<int:pk>/reject/', views.reject_service_report, name='reject_service_report'),
    path('client-sign/form/<int:pk>/', views.client_sign_report, name='client_sign_form'),
    path("client-sign/<int:pk>/", views.client_sign_view, name="client_sign"),
    path('service-report/draft/', views.autosave_service_report, name='service_report_draft'),
    path('service-report/draft/<int:pk>/', views.get_report_draft, name='get_report_draft'),




    path('get-sites/', views.get_sites, name='get_sites'),

    # general report 
    path('generalreport/', views.generalreport, name='generalreport'),  # Match to this URL
    path('view-reports/', views.generalreportsnew, name='generalreportsnew'),
    path('edit-report/<int:report_id>/', views.edit_general_report, name='edit_general_report'),
    path('report/<int:report_id>/pdf/', views.generate_report_pdf, name='generate_report_pdf'),
    path('generalreport/<int:report_id>/edit-history/', views.view_edit_history, name='view_edit_history'),
    # MOM
    path('mom/', views.mom, name='mom'),  # Match to this URL
    path('mom/new/', views.mom_new, name='mom_new'),  # New view to display records
    path('mom/detail/<int:mom_id>/', views.mom_detail, name='mom_detail'),  # View individual MOM details
    path('mom/edit/<int:mom_id>/', views.mom_edit, name='mom_edit'),
    path('mom/<int:mom_id>/download-pdf/', views.pdf_mom, name='pdf_mom'),
    path('mom/<int:mom_id>/details-with-history/', views.mom_details_with_history, name='mom_details_with_history'),
    # Maintenance Checklist 
    path('maintenance-checklist/', views.maintenance_checklist, name='maintenance_checklist'),
    path('maintenance-records/', views.maintenance_checklist_records, name='maintenance_checklist_records'),
    path('maintenance-checklist/edit/<int:id>/', views.edit_maintenance_checklist, name='edit_maintenance_checklist'),
    path('maintenance-checklist/<int:checklist_id>/download-pdf/', views.pdf_maintenance_checklist, name='pdf_maintenance_checklist'),
    path('maintenance-checklist/detail/<int:checklist_id>/', views.maintenance_checklist_detail, name='maintenance_checklist_detail'),
    path('checklist/<int:pk>/<str:action>/', views.update_status, name='update_status'),

    # Generator Report
    path('generatorreport-viewing/', views.generator_report, name='generator_report'),
    path('generatorreport/add/', views.add_generator_report, name='add_generator_report'),
    path('generatorreport/edit/<int:report_id>/', views.edit_generator_report, name='edit_generator_report'),
    path('site-amc/', views.site_amc_management, name='site_amc_management'),
    path('site-amc/<int:amc_id>/upload-water-reports/', views.upload_site_amc_water_reports, name='upload_site_amc_water_reports'),
    path('site-amc/water-report/<int:report_id>/delete/', views.delete_site_amc_water_report, name='delete_site_amc_water_report'),
    # path('demo/', views.demo, name='demo'),



    # export
    path('export/data/', exportviews.export_data, name='export_data'),  # General Report Export
    path('export/mom/', exportviews.export_mom, name='export_mom'),     # MOM Export
    path('export/csv/', exportviews.export_maintenance_checklist_csv, name='export_maintenance_checklist_csv'),
    path('export/pdf/', exportviews.export_maintenance_checklist_pdf, name='export_maintenance_checklist_pdf'),
    path('export/xlsx/', exportviews.export_maintenance_checklist_xlsx, name='export_maintenance_checklist_xlsx'),
    path('service-reports/export/pdf/', exportviews.export_service_reports_pdf, name='export_service_reports_pdf'),
    path('service-reports/bulk-download/', views.bulk_download_service_reports, name='bulk_download_service_reports'),
    path('service-reports/export/csv/', exportviews.export_service_reports_csv, name='export_service_reports_csv'),
    path('service-reports/export/xlsx/', exportviews.export_service_reports_xlsx, name='export_service_reports_xlsx'),
    path('service-report/draft/', views.autosave_service_report, name='service_report_draft'),
    path('service-report/draft/<int:pk>/', views.get_report_draft, name='get_report_draft'),



    path('password_reset/', auth_views.PasswordResetView.as_view(
        html_email_template_name='registration/password_reset_email_html.html'
    ), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # Bike Maintenance
    path('bike-maintenance/', views.bike_maintenance_viewing, name='bike_maintenance_viewing'),
    path('bike-maintenance/add/', views.bike_maintenance_create, name='bike_maintenance_create'),

    # Service Expiry
    path('service-expiry/', views.service_expiry_management, name='service_expiry_management'),
    path('service-expiry/delete/<int:expiry_id>/', views.delete_service_expiry, name='delete_service_expiry'),

]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)