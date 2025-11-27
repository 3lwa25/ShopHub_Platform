"""
URL Configuration for Products App
"""
from django.urls import path
from . import views
from . import seller_views
from . import search_views

app_name = 'products'

urlpatterns = [
    # Public product views
    path('', views.product_list_view, name='product_list'),
    path('search/', views.search_products_view, name='search'),
    path('autocomplete/', views.product_autocomplete_view, name='autocomplete'),
    path('category/<slug:slug>/', views.category_products_view, name='category_products'),
    path('quick-view/<slug:slug>/', views.quick_view_ajax, name='quick_view'),
    path('<slug:slug>/', views.product_detail_view, name='product_detail'),
    
    # Seller product management
    path('seller/products/', seller_views.seller_product_list, name='seller_products'),
    path('seller/products/add/', seller_views.seller_product_add, name='seller_add_product'),
    path('seller/products/<int:pk>/edit/', seller_views.seller_product_edit, name='seller_edit_product'),
    path('seller/products/<int:pk>/delete/', seller_views.seller_product_delete, name='seller_delete_product'),
    path('seller/products/bulk-update/', seller_views.seller_product_bulk_update, name='seller_product_bulk_update'),
    
    # Advanced search and recommendations
    path('search/advanced/', search_views.advanced_search_view, name='advanced_search'),
    path('search/suggestions/', search_views.search_suggestions_api, name='search_suggestions'),
    path('search/history/', search_views.search_history_view, name='search_history'),
    path('track-view/<int:product_id>/', search_views.track_product_view, name='track_view'),
    path('recommendations/', search_views.recommendations_for_user, name='recommendations'),
    path('similar/<int:product_id>/', search_views.similar_products_api, name='similar_products'),
    path('trending/', search_views.trending_products_view, name='trending'),
    path('recently-viewed/', search_views.recently_viewed_view, name='recently_viewed'),
]

