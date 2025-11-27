"""
Utility functions for accounts app
"""
from django.contrib.auth import get_user_model

User = get_user_model()


def is_seller_approved(user):
    """
    Check if user is a seller and is approved
    """
    if not user.is_authenticated:
        return False
    
    if not user.is_seller:
        return False
    
    try:
        return user.seller_profile.is_approved
    except AttributeError:
        return False


def get_seller_profile(user):
    """
    Safely get seller profile
    """
    if not user.is_authenticated or not user.is_seller:
        return None
    
    try:
        return user.seller_profile
    except AttributeError:
        return None


def can_user_shop(user):
    """
    Check if user can add items to cart and checkout
    Sellers cannot shop, only buyers can
    """
    if not user.is_authenticated:
        return True  # Anonymous users can shop
    
    return not user.is_seller  # Only non-sellers can shop

