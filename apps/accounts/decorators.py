"""
Custom decorators for role-based access control
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def buyer_required(view_func):
    """
    Decorator to restrict access to buyers only.
    Sellers and non-authenticated users are redirected.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_seller:
            messages.error(request, 'This feature is only available to buyers. Sellers cannot make purchases.')
            return redirect('seller:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def seller_required(view_func):
    """
    Decorator to restrict access to sellers only.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_seller:
            messages.error(request, 'This feature is only available to sellers.')
            return redirect('core:home')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def approved_seller_required(view_func):
    """
    Decorator to restrict access to approved sellers only.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_seller:
            messages.error(request, 'This feature is only available to sellers.')
            return redirect('core:home')
        
        # Check if seller is approved
        try:
            seller_profile = request.user.seller_profile
            if not seller_profile.is_approved:
                messages.warning(request, 'Your seller account is pending approval. You will be notified once approved.')
                return redirect('accounts:seller_pending')
        except AttributeError:
            messages.error(request, 'Seller profile not found.')
            return redirect('core:home')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_required(view_func):
    """
    Decorator to restrict access to admin users only.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_admin_user:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def not_seller(view_func):
    """
    Decorator to prevent sellers from accessing buyer-specific views.
    Used for cart, checkout, etc.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_seller:
            messages.info(request, 'Sellers cannot access this feature. This is for buyers only.')
            return redirect('accounts:seller_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

