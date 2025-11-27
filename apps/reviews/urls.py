"""
URLs for Product Reviews
"""
from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    # Write/Edit Reviews
    path('write/<int:order_item_id>/', views.write_review_view, name='write_review'),
    path('edit/<int:review_id>/', views.edit_review_view, name='edit_review'),
    path('delete/<int:review_id>/', views.delete_review_view, name='delete_review'),
    
    # View Reviews
    path('product/<int:product_id>/', views.product_reviews_view, name='product_reviews'),
    
    # Helpful Voting
    path('helpful/<int:review_id>/', views.mark_helpful_view, name='mark_helpful'),
    
    # Seller Response
    path('respond/<int:review_id>/', views.seller_respond_view, name='seller_respond'),
]

