"""
URL Configuration for Core App
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('search/autocomplete/', views.search_autocomplete, name='search_autocomplete'),
]

