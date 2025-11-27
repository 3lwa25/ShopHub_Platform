"""
Notification Context Processor
"""
from .models import Notification


def notification_context(request):
    """
    Add notification count to all templates
    """
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        recent_notifications = Notification.objects.filter(
            user=request.user
        )[:5]
    else:
        unread_count = 0
        recent_notifications = []
    
    return {
        'notification_unread_count': unread_count,
        'recent_notifications': recent_notifications,
    }

