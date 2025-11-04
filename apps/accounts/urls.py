"""
URL Configuration for Accounts App
"""
from django.urls import path
from . import views

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
    path('seller/dashboard/', views.seller_dashboard_view, name='seller_dashboard'),
]

