"""
URL Configuration for Shopping Cart
"""
from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    # Cart view
    path('', views.cart_view, name='cart_view'),
    
    # Cart actions
    path('add/', views.add_to_cart, name='add_to_cart'),
    path('update/<int:item_id>/', views.update_cart_item, name='update_cart_item'),
    path('remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('clear/', views.clear_cart, name='clear_cart'),
    
    # AJAX endpoints
    path('count/', views.cart_count, name='cart_count'),
]

