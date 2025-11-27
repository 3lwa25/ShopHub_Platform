"""
URL Configuration for Accounts App
"""
from django.urls import path
from . import views
from . import seller_views
from . import admin_views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Profile
    path('profile/', views.profile_view, name='profile'),
    
    # Seller Profile
    path('seller/profile/create/', views.seller_profile_create_view, name='seller_profile_create'),
    path('seller/profile/edit/', views.seller_profile_edit_view, name='seller_profile_edit'),
    path('seller/pending/', seller_views.seller_pending, name='seller_pending'),
    path('seller/dashboard/', seller_views.seller_dashboard, name='seller_dashboard'),
    path('seller/analytics/', seller_views.seller_analytics, name='seller_analytics'),
    
    # Admin Dashboard
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('admin/users/', admin_views.admin_users_list, name='admin_users_list'),
    path('admin/users/<int:user_id>/edit/', admin_views.admin_user_edit, name='admin_user_edit'),
    path('admin/products/', admin_views.admin_products_manage, name='admin_products_manage'),
    path('admin/orders/', admin_views.admin_orders_manage, name='admin_orders_manage'),
    path('admin/sellers/<int:seller_id>/approve/', admin_views.admin_approve_seller, name='admin_approve_seller'),
]

