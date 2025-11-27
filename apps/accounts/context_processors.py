"""
Context processors for accounts app
"""
from .utils import is_seller_approved, can_user_shop


def user_role_context(request):
    """
    Add user role information to template context
    """
    context = {
        'is_buyer': False,
        'is_seller': False,
        'is_approved_seller': False,
        'is_admin': False,
        'can_shop': True,  # Anonymous users can shop
    }
    
    if request.user.is_authenticated:
        context['is_buyer'] = request.user.is_buyer
        context['is_seller'] = request.user.is_seller
        context['is_admin'] = request.user.is_admin_user
        context['is_approved_seller'] = is_seller_approved(request.user)
        context['can_shop'] = can_user_shop(request.user)
    
    return context

