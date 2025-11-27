"""
Signals for Accounts App
"""
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.utils import timezone
from apps.common.notifications import notify_buyer_login, notify_seller_login


@receiver(user_logged_in)
def send_login_notification(sender, request, user, **kwargs):
    """Send email notification when user logs in."""
    if not user or not user.email:
        return
    
    login_time = timezone.now()
    ip_address = request.META.get('REMOTE_ADDR')
    
    if user.is_seller and hasattr(user, 'seller_profile'):
        notify_seller_login(user, user.seller_profile, login_time, ip_address)
    elif user.is_buyer:
        notify_buyer_login(user, login_time, ip_address)

