"""
Custom Middleware for Shop Hub
"""
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages


class GuestUserRestrictionMiddleware:
    """
    Middleware to restrict guest users from accessing certain pages
    """
    
    # URLs that guests CAN access
    ALLOWED_URLS = [
        '/accounts/login/',
        '/accounts/register/',
        '/accounts/logout/',
        '/',  # Homepage
        '/products/',  # Product listing
        '/static/',
        '/media/',
        '/admin/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if user is guest (not authenticated)
        if not request.user.is_authenticated:
            # Check if URL is not in allowed list
            is_allowed = False
            for allowed_url in self.ALLOWED_URLS:
                if request.path.startswith(allowed_url):
                    is_allowed = True
                    break
            
            # Also allow product detail pages
            if request.path.startswith('/products/') and not request.path.startswith('/products/seller/'):
                is_allowed = True
            
            # If not allowed, redirect to login
            if not is_allowed:
                messages.warning(request, 'Please login to access this feature.')
                return redirect(f"{reverse('accounts:login')}?next={request.path}")
        
        response = self.get_response(request)
        return response

