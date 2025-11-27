"""
Context Processors for Rewards System
Makes reward data available in all templates
"""
from .models import RewardAccount
from apps.notifications.models import Notification


def rewards_context(request):
    """
    Add reward account information and notifications to template context.
    Available in all templates as {{ reward_account }} and {{ notification_unread_count }}
    """
    from django.urls import reverse
    
    context = {
        'reward_account': None,
        'has_rewards': False,
        'notification_unread_count': 0,
        'unread_notifications_count': 0,  # Alias for compatibility
        'recent_notifications': [],
        'home_url': reverse('core:home'),  # Provide home URL for templates
    }
    
    if request.user.is_authenticated:
        # Reward account
        try:
            reward_account = RewardAccount.objects.get(user=request.user)
            context['reward_account'] = reward_account
            context['has_rewards'] = True
        except RewardAccount.DoesNotExist:
            # Create reward account on the fly
            reward_account = RewardAccount.objects.create(
                user=request.user,
                points_balance=0,
                total_earned=0,
                total_spent=0,
                tier='bronze'
            )
            context['reward_account'] = reward_account
            context['has_rewards'] = True
        
        # Notifications
        unread_count = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        recent_notifications = Notification.objects.filter(
            user=request.user
        ).order_by('-created_at')[:5]
        
        context['notification_unread_count'] = unread_count
        context['unread_notifications_count'] = unread_count  # Alias
        context['recent_notifications'] = recent_notifications
    
    return context

