"""
Signals for Rewards System
Auto-award points when orders are delivered
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from apps.orders.models import Order
from .models import RewardAccount, PointsTransaction


@receiver(post_save, sender=Order)
def award_points_on_order_completion(sender, instance, created, **kwargs):
    """
    Award reward points when order status changes to DELIVERED.
    Only award points once per order.
    """
    # Only process for authenticated buyers
    if not instance.buyer:
        return
    
    # Only award points when order is delivered
    if instance.status != 'DELIVERED':
        return
    
    # Check if points already awarded for this order
    if instance.points_earned > 0:
        # Check if transaction already exists
        existing_transaction = PointsTransaction.objects.filter(
            order=instance,
            user=instance.buyer,
            transaction_type='earned'
        ).exists()
        
        if existing_transaction:
            return  # Points already awarded
    
    # Calculate points to award
    points_to_award = instance.calculate_points_earned()
    
    if points_to_award <= 0:
        return
    
    # Update order with points earned
    if instance.points_earned != points_to_award:
        instance.points_earned = points_to_award
        instance.save(update_fields=['points_earned'])
    
    # Get or create reward account
    reward_account, created = RewardAccount.objects.get_or_create(
        user=instance.buyer,
        defaults={
            'points_balance': 0,
            'total_earned': 0,
            'total_spent': 0,
            'tier': 'bronze'
        }
    )
    
    # Award points
    reward_account.add_points(
        amount=points_to_award,
        transaction_type='earned',
        order=instance,
        description=f'Purchase reward for order {instance.order_number}'
    )
    
    # Send email notification
    try:
        from .views import send_points_earned_email, create_notification
        send_points_earned_email(instance.buyer, points_to_award, instance)
        
        # Create in-app notification
        create_notification(
            user=instance.buyer,
            notification_type='points_earned',
            title=f'{points_to_award} Points Earned!',
            message=f'You earned {points_to_award} points for your order #{instance.order_number}',
            link=f'/orders/my-orders/{instance.order_number}/'
        )
    except Exception as e:
        print(f"Error sending notifications: {e}")
    
    print(f"✅ Awarded {points_to_award} points to {instance.buyer.email} for order {instance.order_number}")


@receiver(post_save, sender=Order)
def handle_order_cancellation_refund(sender, instance, **kwargs):
    """
    Refund points if order is cancelled or refunded after points were awarded.
    """
    # Only process if order is cancelled or refunded
    if instance.status not in ['CANCELLED', 'REFUNDED']:
        return
    
    # Check if points were earned for this order
    if instance.points_earned <= 0:
        return
    
    # Check if points are already refunded
    refund_transaction = PointsTransaction.objects.filter(
        order=instance,
        user=instance.buyer,
        transaction_type='adjustment',
        amount__lt=0
    ).exists()
    
    if refund_transaction:
        return  # Already refunded
    
    # Get reward account
    try:
        reward_account = RewardAccount.objects.get(user=instance.buyer)
    except RewardAccount.DoesNotExist:
        return  # No reward account
    
    # Deduct points (if balance allows, otherwise set to 0)
    points_to_deduct = min(instance.points_earned, reward_account.points_balance)
    
    if points_to_deduct > 0:
        # Create adjustment transaction
        reward_account.points_balance -= points_to_deduct
        reward_account.total_earned -= points_to_deduct
        reward_account.save(update_fields=['points_balance', 'total_earned', 'updated_at'])
        
        PointsTransaction.objects.create(
            user=instance.buyer,
            order=instance,
            transaction_type='adjustment',
            amount=-points_to_deduct,
            balance_after=reward_account.points_balance,
            description=f'Points refund for cancelled order {instance.order_number}'
        )
        
        # Update tier
        reward_account.update_tier()
        
        print(f"♻️ Refunded {points_to_deduct} points from {instance.buyer.email} for cancelled order {instance.order_number}")

