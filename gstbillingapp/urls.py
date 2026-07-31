from django.urls import path
from django.urls import include
from django.contrib.auth.views import LogoutView
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),

    path('invoices/new', views.invoice_create, name='invoice_create'),
    path('invoices/delete', views.invoice_delete, name='invoice_delete'),

    path('login', views.login_view, name='login_view'),
    path('signup', views.signup_view, name='signup_view'),
    path('accounts/', include('django.contrib.auth.urls')),

    path('invoices', views.invoices, name='invoices'),
    path('invoice/<int:invoice_id>', views.invoice_viewer, name='invoice_viewer'),

    path('credit_notes/new', views.credit_note_create, name='credit_note_create'),
    path('credit_notes/delete', views.credit_note_delete, name='credit_note_delete'),
    path('credit_notes', views.credit_notes, name='credit_notes'),
    path('credit_note/<int:credit_note_id>', views.credit_note_viewer, name='credit_note_viewer'),
    path("credit_notes/<int:credit_note_id>/edit/", views.credit_note_edit, name="credit_note_edit"),

    path('customers', views.customers, name='customers'),
    path('customers/add', views.customer_add, name='customer_add'),
    path('customers/edit/<int:customer_id>', views.customer_edit, name='customer_edit'),
    path('customers/delete', views.customer_delete, name='customer_delete'),
    path('customersjson', views.customersjson, name='customersjson'),

    path('products', views.products, name='products'),
    path('products/add', views.product_add, name='product_add'),
    path('products/edit/<int:product_id>', views.product_edit, name='product_edit'),
    path('products/delete', views.product_delete, name='product_delete'),
    path('productsjson', views.productsjson, name='productsjson'),

    path('profile', views.user_profile, name='user_profile'),
    path('profile/edit', views.user_profile_edit, name='user_profile_edit'),


    path('Display-banks', views.display_bank, name='displaybanks'),
    path('Bank', views.add_bank, name='banks'),

    path('get-all-vehicle-numbers-by-name/', views.get_all_vehicle_numbers_by_name, name='get_all_vehicle_numbers_by_name'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path("invoices/<int:invoice_id>/edit/", views.invoice_edit, name="invoice_edit"),

    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
]