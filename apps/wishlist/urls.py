"""
URLs for Wishlist
"""
from django.urls import path
from . import views

app_name = 'wishlist'

urlpatterns = [
    # Wishlist Management
    path('', views.wishlist_view, name='wishlist'),
    path('add/<int:product_id>/', views.add_to_wishlist_view, name='add'),
    path('remove/<int:item_id>/', views.remove_from_wishlist_view, name='remove'),
    path('toggle/<int:product_id>/', views.toggle_wishlist_view, name='toggle'),
    path('move-to-cart/<int:item_id>/', views.move_to_cart_view, name='move_to_cart'),
    path('edit/<int:item_id>/', views.edit_wishlist_item_view, name='edit_item'),
    path('clear/', views.clear_wishlist_view, name='clear'),
    
    # Status Check
    path('check/<int:product_id>/', views.check_wishlist_status, name='check_status'),
]

