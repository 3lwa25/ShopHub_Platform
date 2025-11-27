from django.urls import path
from . import views
from . import coupon_views

app_name = 'orders'

urlpatterns = [
    # Checkout
    path('checkout/', views.checkout_view, name='checkout'),
    path('checkout/success/', views.checkout_success_view, name='checkout_success'),

    # Buyer views
    path('my-orders/', views.buyer_orders_view, name='buyer_orders'),
    path('my-orders/<str:order_number>/', views.buyer_order_detail_view, name='buyer_order_detail'),
    path('my-orders/<str:order_number>/tracking/', views.buyer_order_tracking_view, name='buyer_order_tracking'),
    path('my-orders/<str:order_number>/payment/', views.payment_method_view, name='payment_method'),
    path('my-orders/<str:order_number>/payment/process/', views.payment_process_view, name='payment_process'),
    path('my-orders/<str:order_number>/invoice/', views.invoice_download_view, name='invoice_download'),
    path('my-orders/<str:order_number>/refund/', views.request_refund_view, name='request_refund'),
    path('my-orders/payments/history/', views.buyer_payment_history_view, name='buyer_payment_history'),

    # Seller views
    path('seller/', views.seller_orders_view, name='seller_orders'),
    path('seller/<str:order_number>/', views.seller_order_detail_view, name='seller_order_detail'),
    path('seller/<str:order_number>/items/<int:item_id>/status/', views.seller_update_order_item_status, name='seller_item_status'),
    path('seller/<str:order_number>/tracking/', views.seller_order_tracking_view, name='seller_order_tracking'),
    path('seller/payments/history/', views.seller_payment_history_view, name='seller_payment_history'),
    
    # Payment approval
    path('approve-payment/<int:order_id>/', views.approve_payment_view, name='approve_payment'),
    
    # Coupon views
    path('coupons/validate/', coupon_views.validate_coupon_view, name='validate_coupon'),
    path('coupons/apply/', coupon_views.apply_coupon_view, name='apply_coupon'),
    path('coupons/remove/', coupon_views.remove_coupon_view, name='remove_coupon'),
    path('coupons/available/', coupon_views.available_coupons_view, name='available_coupons'),
]
