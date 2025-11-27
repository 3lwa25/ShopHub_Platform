"""
Virtual Try-On URL Configuration
"""
from django.urls import path
from . import views

app_name = 'virtual_tryon'

urlpatterns = [
    # VTO Pages
    path('', views.vto_home, name='vto_home'),
    path('tryon/<int:product_id>/', views.vto_tryon, name='vto_tryon'),
    path('history/', views.vto_history, name='vto_history'),
    
    # API Endpoints
    path('api/upload/', views.vto_upload_photo, name='vto_upload'),
    path('api/save-result/', views.vto_save_result, name='vto_save_result'),
    path('api/delete/', views.vto_delete_photo, name='vto_delete'),
    path('api/analyze-image/', views.vto_analyze_image, name='vto_analyze_image'),
    path('api/remove-background/', views.vto_remove_background, name='vto_remove_background'),
]

