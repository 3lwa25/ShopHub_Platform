"""
URL Configuration for Rewards App
"""
from django.urls import path
from . import views

app_name = 'rewards'

urlpatterns = [
    # Main dashboard
    path('', views.rewards_dashboard, name='dashboard'),
    
    # Transaction history
    path('history/', views.transaction_history, name='history'),
    
    # Redemption
    path('redeem/', views.redeem_points, name='redeem'),
    
    # Information pages
    path('tiers/', views.tier_information, name='tier_info'),
    path('earn/', views.earn_points_info, name='earn_info'),
    
    # Notifications
    path('notifications/', views.notifications_center, name='notifications'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_read'),
    
    # Points Gifting
    path('gift/', views.gift_points_view, name='gift_points'),
    path('gift/history/', views.gift_history, name='gift_history'),
    
    # AJAX endpoints
    path('api/balance/', views.get_points_balance, name='api_balance'),
    path('api/quick-redeem/', views.quick_redeem, name='api_quick_redeem'),
]

