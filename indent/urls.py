from . import views
from . import views_kitting
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from django.contrib.auth.views import LoginView, LogoutView

from django.urls import re_path


urlpatterns = [
    
    path('', views.dashboard, name='indent_dashboard'),
    path('home/', views.dashboard, name='indent_dashboard'),
    path('api/sfg-stock-search/', views.sfg_stock_search, name='sfg_stock_search'),
    path('indent_list', views.indent_list, name='indent_list'),
    path('new/', views.indent_create, name='indent_create'),
    path('permissions/', views.manage_permissions, name='manage_permissions'),
    path('<int:pk>/approve/', views.indent_approve, name='indent_approve'),
    path("indent/<int:pk>/convert/<int:vendor_id>/", views.indent_convert_to_po, name="indent_convert_to_po"),
    path("indent/convert-combined/", views.indent_convert_to_po, name="indent_convert_combined"),
    path('stock/', views.stock_list, name='stock_list'),
    path("purchase-orders/", views.purchase_order_list, name="purchase_order_list"),
    path("purchase-orders/<int:pk>/", views.purchase_order_detail, name="purchase_order_detail"),
    path('indent/<int:pk>/reject/', views.indent_reject, name='indent_reject'),
    path('purchase_order/<int:pk>/approve/', views.purchase_order_approve, name='purchase_order_approve'),
    path('purchase_order/<int:pk>/reject/', views.purchase_order_reject, name='purchase_order_reject'),
    path('vendors/', views.vendor_list, name='vendor_list'),
    path('vendors/<int:pk>/rate/', views.vendor_rate, name='vendor_rate'),
    path('vendors/sync-ratings/', views.sync_vendor_ratings, name='sync_vendor_ratings'),
    path('vendors/export-template/', views.export_vendor_template, name='export_vendor_template'),
    path('vendors/import/', views.import_vendors, name='import_vendors'),

    path('stock/export-template/', views.export_stock_template, name='export_stock_template'),
    path('stock/import/', views.import_stock, name='import_stock'),

    path('purchase-orders-list/', views.po_list, name='po_list'),
    path('purchase-orders/<int:pk>/update-delay/', views.po_update_delay, name='po_update_delay'),

    path("grn/", views.grn_list, name="grn_list"),
    path("grn/create/<int:po_id>/", views.create_grn, name="create_grn"),


    path("index", views.index, name="index"),
    path("generate-bom/", views.generate_bom, name="generate_bom"),
    path("api/product/<str:code>/", views.product_lookup, name="product_lookup"),
    path("product/<str:code>/", views.product_detail, name="product_detail"),
    path('vendor-autocomplete/', views.vendor_autocomplete, name='vendor_autocomplete'),


    path("production-orders/", views.production_orders, name="production_orders"),
    path("production-orders/create/", views.create_production_order, name="create_production_order"),
    # path("production-orders/<int:po_id>/indent/", views.create_indent, name="create_indent"),
     path("production-order-list", views.production_order_list, name="production_order_list"),
    path("create/production_order", views.production_order_create, name="production_order_create"),
    path("production_order_detail/<int:pk>/", views.production_order_detail, name="production_order_detail"),
    path("indents/<int:indent_id>/process/", views.process_indent, name="process_indent"),
    path('indents/<int:pk>/', views.indent_detail, name='indent_detail'),

    path("production_order/<int:production_order_id>/issue/", views.material_issue_create, name="material_issue_create"),
    path("production_order/<int:production_order_id>/qc/", views.qc_check_create, name="qc_check_create"),
    path("production_order/<int:production_order_id>/delivery/", views.delivery_create, name="delivery_create"),
    path("stock/<int:stock_id>/quantity/", views.get_stock_quantity, name="get_stock_quantity"),
    path("project/<int:project_id>/issue-material/", views.project_material_issue, name="project_material_issue"),
    path("project/<int:project_id>/issue-from-indent/", views.project_material_issue_from_indent, name="project_material_issue_from_indent"),
    path("project/<int:project_id>/issue-from-indent/<int:indent_id>/", views.project_material_issue_from_indent, name="project_material_issue_from_indent_detail"),
    path('snag/resolve/<int:snag_id>/', views.resolve_snag, name='resolve_snag'),
    path("department-flow/", views.department_flow, name="department_flow"),



    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.project_create_ajax, name='project_create_ajax'),
    path("projects/<int:pk>/", views.project_detail, name="project_detail"),
    path("project/<int:project_id>/assembly/", views.project_assembly, name="project_assembly"),
    path("client/project/<uuid:token>/assembly/", views.client_project_assembly, name="client_project_assembly"),
    path("project/<int:project_id>/deploy/", views.project_deploy, name="project_deploy"),
    path("deployment/<int:deployment_id>/", views.deployment_details, name="deployment_details"),
    path("deployment/<int:deployment_id>/warranty/", views.generate_warranty, name="generate_warranty"),
    path("deployment/<int:deployment_id>/guarantee/", views.generate_guarantee, name="generate_guarantee"),
    path("deployment/<int:deployment_id>/dc/", views.generate_dc, name="generate_dc"),
    path("deployment/<int:deployment_id>/commissioning/", views.generate_commissioning, name="generate_commissioning"),
    path("deployment/<int:deployment_id>/handover/", views.generate_handover, name="generate_handover"),
    path("deployment/<int:deployment_id>/attach-doc/", views.attach_generated_doc, name="attach_generated_doc"),
    path("internal-item/<int:pk>/delete/", views.internal_item_delete, name="internal_item_delete"),  # optional
    path("projects/<int:project_id>/department/<int:dept_id>/raise-indent/", views.project_indent_create, name="project_indent_create"),
    path("projects/<int:project_id>/department/<int:dept_id>/indents/", views.project_department_indents, name="project_department_indents"),
    path("indent/<int:indent_id>/details/", views.indent_details, name="indent_details"),
    path("indent/item/<int:item_id>/update/", views.update_indent_item, name="update_indent_item"),
    


    path("grn/internal/<int:indent_id>/", views.create_internal_grn, name="create_internal_grn"),
    path("internal-requirement/<int:item_id>/issue/", views.issue_internal_requirement, name="issue_internal_requirement"),
    path("projects/<int:project_id>/financial-dashboard/", views.project_financial_dashboard, name="project_financial_dashboard"),
    path("projects/edit/<int:pk>/", views.project_edit_ajax, name="project_edit_ajax"),
    path("edit/<int:pk>/", views.indent_edit_ajax, name="indent_edit_ajax"),

    path("purchase-order/<int:po_id>/print/", views.purchase_order_print, name="purchase_order_print"),
    path('email-logs/', views.email_log_list, name='email_log_list'),
    path("project/<int:project_id>/cross-dept-request/", views.create_cross_dept_request, name="create_cross_dept_request"),


    path("project/<int:project_id>/check-vendors-print/", views.check_project_vendors_for_print, name="check_project_vendors_print"),

    path("project/<int:project_id>/combined-po-print/<int:vendor_id>/", views.project_combined_po_print, name="project_combined_po_print"),

    


    path('payments/', views.vendor_payments_board, name='vendor_payments_board'),
    path('payments/vendor/<int:vendor_id>/checkout/', views.vendor_po_payment_checkout, name='vendor_po_payment_checkout'),
    path('payments/vendor/<int:vendor_id>/history/', views.vendor_payment_history, name='vendor_payment_history'),
    path('payments/weekly-outlook/', views.weekly_payment_forecast, name='weekly_payment_forecast'),
    
    # Kitting URLs
    path('kitting/upload/', views_kitting.upload_kit_excel, name='upload_kit_excel'),
    path('kitting/kits/', views_kitting.machine_kits_list, name='machine_kits_list'),
    path('kitting/kits/<int:kit_id>/', views_kitting.machine_kit_detail, name='machine_kit_detail'),
    path('production-orders/<int:po_id>/kitting-dashboard/', views_kitting.po_kitting_dashboard, name='po_kitting_dashboard'),
    path('projects/<int:project_id>/kitting-dashboard/', views_kitting.project_kitting_dashboard, name='project_kitting_dashboard'),
    path('production-orders/<int:po_id>/attach-kit/', views_kitting.attach_kit_to_po, name='attach_kit_to_po'),
    path('kitting/download-template/', views_kitting.download_kit_template, name='download_kit_template'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)