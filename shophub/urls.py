"""
URL configuration for Shop Hub project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Accounts (Authentication)
    path('accounts/', include('apps.accounts.urls')),
    
    # Products
    path('products/', include('apps.products.urls')),
    
    # Shopping Cart
    path('cart/', include('apps.cart.urls')),
    
    # Orders & Checkout
    path('orders/', include('apps.orders.urls')),
    
    # Reviews & Ratings
    path('reviews/', include('apps.reviews.urls')),
    
    # Rewards & Loyalty
    path('rewards/', include('apps.rewards.urls')),
    
    # Notifications Center
    path('notifications/', include(('apps.notifications.urls', 'notifications'), namespace='notifications')),
    
    # Wishlist
    path('wishlist/', include('apps.wishlist.urls')),
    
    # AI Chatbot
    path('chatbot/', include('apps.ai_chatbot.urls')),
    
    # Virtual Try-On
    path('virtual-tryon/', include('apps.virtual_tryon.urls', namespace='virtual_tryon')),
    
    # Core (Homepage and main navigation)
    path('', include('apps.core.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Django Debug Toolbar
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

# Custom admin site settings
admin.site.site_header = "Shop Hub Admin"
admin.site.site_title = "Shop Hub Admin Portal"
admin.site.index_title = "Welcome to Shop Hub Administration"

