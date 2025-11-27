"""
Rewards System Views for Shop Hub
Handles reward points, transactions, and redemption
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from django.utils import timezone
from django.utils.html import format_html
from decimal import Decimal
from .models import RewardAccount, PointsTransaction, Reward, RewardRedemption
from apps.notifications.models import Notification
from apps.orders.models import Order


@login_required
def rewards_dashboard(request):
    """
    Main rewards dashboard showing points balance, tier, and stats.
    """
    # Get or create reward account
    reward_account, created = RewardAccount.objects.get_or_create(
        user=request.user,
        defaults={
            'points_balance': 0,
            'total_earned': 0,
            'total_spent': 0,
            'tier': 'bronze'
        }
    )
    
    # Get recent transactions (last 5)
    recent_transactions = PointsTransaction.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    # Calculate statistics
    this_month_earned = PointsTransaction.objects.filter(
        user=request.user,
        transaction_type__in=['earned', 'bonus', 'referral'],
        created_at__month=timezone.now().month,
        created_at__year=timezone.now().year
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # Calculate next tier requirements
    tier_thresholds = {
        'bronze': {'min': 0, 'max': 1999, 'next': 'Silver', 'points_needed': 2000},
        'silver': {'min': 2000, 'max': 4999, 'next': 'Gold', 'points_needed': 5000},
        'gold': {'min': 5000, 'max': 9999, 'next': 'Platinum', 'points_needed': 10000},
        'platinum': {'min': 10000, 'max': float('inf'), 'next': 'Max Level', 'points_needed': None},
    }
    
    current_tier_info = tier_thresholds.get(reward_account.tier, tier_thresholds['bronze'])
    if reward_account.tier == 'platinum':
        points_to_next_tier = 0
        progress_percentage = 100
    else:
        points_to_next_tier = current_tier_info['points_needed'] - reward_account.total_earned
        tier_range = current_tier_info['max'] - current_tier_info['min'] + 1
        progress_in_tier = reward_account.total_earned - current_tier_info['min']
        progress_percentage = min(100, (progress_in_tier / tier_range) * 100)
    
    # Get available rewards from database (admin-manageable)
    all_rewards = Reward.objects.filter(is_active=True).order_by('display_order', 'points_required')
    available_rewards = []
    
    for reward in all_rewards:
        available_rewards.append({
            'id': reward.id,
            'name': reward.name,
            'points': reward.points_required,
            'description': reward.description,
            'icon': reward.icon,
            'reward_type': reward.reward_type,
            'is_available': reward.is_available(request.user),
            'can_redeem': reward.can_redeem(request.user),
            'tier_required': reward.tier_required,
            'is_limited_time': reward.is_limited_time,
            'end_date': reward.end_date,
        })
    
    context = {
        'reward_account': reward_account,
        'recent_transactions': recent_transactions,
        'this_month_earned': this_month_earned,
        'current_tier_info': current_tier_info,
        'points_to_next_tier': points_to_next_tier,
        'progress_percentage': progress_percentage,
        'available_rewards': available_rewards,
        'tier_benefits': get_tier_benefits(reward_account.tier),
    }
    
    return render(request, 'rewards/dashboard.html', context)


@login_required
def transaction_history(request):
    """
    Display full transaction history with filters and pagination.
    """
    # Get or create reward account
    reward_account, _ = RewardAccount.objects.get_or_create(
        user=request.user,
        defaults={'points_balance': 0}
    )
    
    # Get filter parameters
    transaction_type = request.GET.get('type', '')
    date_range = request.GET.get('range', '')
    
    # Build queryset
    transactions = PointsTransaction.objects.filter(user=request.user)
    
    # Apply filters
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)
    
    if date_range == 'week':
        from datetime import timedelta
        start_date = timezone.now() - timedelta(days=7)
        transactions = transactions.filter(created_at__gte=start_date)
    elif date_range == 'month':
        transactions = transactions.filter(
            created_at__month=timezone.now().month,
            created_at__year=timezone.now().year
        )
    elif date_range == 'year':
        transactions = transactions.filter(
            created_at__year=timezone.now().year
        )
    
    # Pagination
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate statistics
    earned_total = transactions.filter(amount__gt=0).aggregate(total=Sum('amount'))['total'] or 0
    redeemed_total = abs(transactions.filter(amount__lt=0).aggregate(total=Sum('amount'))['total'] or 0)
    
    context = {
        'reward_account': reward_account,
        'page_obj': page_obj,
        'transaction_type': transaction_type,
        'date_range': date_range,
        'earned_total': earned_total,
        'redeemed_total': redeemed_total,
        'transaction_types': PointsTransaction.TRANSACTION_TYPES,
    }
    
    return render(request, 'rewards/transaction_history.html', context)


@login_required
def redeem_points(request):
    """
    Redeem points for rewards/discounts with full coupon integration.
    """
    if request.method == 'POST':
        reward_id = request.POST.get('reward_id')
        
        if not reward_id:
            messages.error(request, 'Invalid reward selected.')
            return redirect('rewards:dashboard')
        
        try:
            # Get reward
            reward = Reward.objects.get(id=reward_id, is_active=True)
        except Reward.DoesNotExist:
            messages.error(request, 'Reward not found or no longer available.')
            return redirect('rewards:dashboard')
        
        # Get reward account
        try:
            reward_account = RewardAccount.objects.get(user=request.user)
        except RewardAccount.DoesNotExist:
            messages.error(request, 'Reward account not found. Please contact support.')
            return redirect('rewards:dashboard')
        
        # Validate redemption
        if not reward.can_redeem(request.user):
            if not reward.is_available(request.user):
                messages.error(request, f'{reward.name} is not currently available.')
            elif reward_account.points_balance < reward.points_required:
                points_needed = reward.points_required - reward_account.points_balance
                messages.error(request, f'Insufficient points. You need {points_needed} more points.')
            else:
                messages.error(request, 'You cannot redeem this reward.')
            return redirect('rewards:dashboard')
        
        # Redeem points
        success = reward_account.redeem_points(
            amount=reward.points_required,
            description=f'Redeemed: {reward.name}'
        )
        
        if not success:
            messages.error(request, 'Failed to redeem points. Please try again.')
            return redirect('rewards:dashboard')
        
        # Generate coupon code for discount vouchers
        coupon_code = ''
        if reward.reward_type == 'discount_voucher' and reward.discount_amount:
            coupon_code = generate_coupon_code(request.user, reward)
        
        # Create redemption record
        redemption = RewardRedemption.objects.create(
            user=request.user,
            reward=reward,
            points_spent=reward.points_required,
            status='completed' if reward.reward_type != 'free_product' else 'pending',
            coupon_code=coupon_code,
            metadata={
                'reward_type': reward.reward_type,
                'reward_name': reward.name,
                'discount_amount': float(reward.discount_amount) if reward.discount_amount else 0,
            }
        )
        
        # Update reward redemption count
        reward.redemption_count += 1
        reward.save(update_fields=['redemption_count'])
        
        # Create notification
        create_notification(
            user=request.user,
            notification_type='reward_redeemed',
            title='Reward Redeemed!',
            message=f'You successfully redeemed {reward.name} for {reward.points_required} points.',
            link='/rewards/history/',
            metadata={'redemption_id': redemption.id}
        )
        
        # Send email notification
        send_redemption_email(request.user, reward, redemption, coupon_code)
        
        # Success message
        success_msg = f'Successfully redeemed {reward.points_required} points for {reward.name}! '
        if coupon_code:
            success_msg += f'Your coupon code is: <strong>{coupon_code}</strong>. '
        success_msg += f'Your new balance is {reward_account.points_balance} points.'
        messages.success(request, format_html(success_msg))
        
        return redirect('rewards:dashboard')
    
    return redirect('rewards:dashboard')


@login_required
def tier_information(request):
    """
    Display tier information and benefits.
    """
    # Get or create reward account
    reward_account, _ = RewardAccount.objects.get_or_create(
        user=request.user,
        defaults={'points_balance': 0}
    )
    
    # Define all tiers with benefits
    tiers = [
        {
            'name': 'Bronze',
            'key': 'bronze',
            'min_points': 0,
            'icon': '🥉',
            'color': 'orange',
            'benefits': [
                'Earn 1 point per EGP spent',
                'Basic customer support',
                'Birthday rewards',
                'Email newsletters',
            ]
        },
        {
            'name': 'Silver',
            'key': 'silver',
            'min_points': 2000,
            'icon': '🥈',
            'color': 'gray',
            'benefits': [
                'All Bronze benefits',
                'Earn 1.5 points per EGP spent',
                'Priority customer support',
                'Exclusive member discounts (5%)',
                'Early access to new products',
            ]
        },
        {
            'name': 'Gold',
            'key': 'gold',
            'min_points': 5000,
            'icon': '🥇',
            'color': 'yellow',
            'benefits': [
                'All Silver benefits',
                'Earn 2 points per EGP spent',
                'Free shipping on all orders',
                'Exclusive member discounts (10%)',
                'VIP customer support',
                'Special birthday gifts',
            ]
        },
        {
            'name': 'Platinum',
            'key': 'platinum',
            'min_points': 10000,
            'icon': '💎',
            'color': 'purple',
            'benefits': [
                'All Gold benefits',
                'Earn 3 points per EGP spent',
                'Personal shopping assistant',
                'Exclusive member discounts (15%)',
                'First access to limited editions',
                'Complimentary gift wrapping',
                'Invitation to VIP events',
                'Priority shipping',
            ]
        },
    ]
    
    context = {
        'reward_account': reward_account,
        'tiers': tiers,
        'current_tier': reward_account.tier,
    }
    
    return render(request, 'rewards/tier_info.html', context)


@login_required
def earn_points_info(request):
    """
    Display information on how to earn points.
    """
    # Get or create reward account
    reward_account, _ = RewardAccount.objects.get_or_create(
        user=request.user,
        defaults={'points_balance': 0}
    )
    
    # Ways to earn points
    earning_methods = [
        {
            'title': 'Make Purchases',
            'description': 'Earn 10 points for every EGP spent',
            'icon': 'shopping-cart',
            'points': '10 pts per EGP'
        },
        {
            'title': 'Write Reviews',
            'description': 'Share your experience with products',
            'icon': 'star',
            'points': '50 pts per review'
        },
        {
            'title': 'Refer Friends',
            'description': 'Invite friends to join Shop Hub',
            'icon': 'users',
            'points': '500 pts per referral'
        },
        {
            'title': 'Birthday Bonus',
            'description': 'Special birthday reward every year',
            'icon': 'gift',
            'points': '200 pts'
        },
        {
            'title': 'Complete Profile',
            'description': 'Fill out your profile completely',
            'icon': 'user-check',
            'points': '100 pts'
        },
        {
            'title': 'Social Media',
            'description': 'Follow us on social platforms',
            'icon': 'share-2',
            'points': '50 pts'
        },
    ]
    
    context = {
        'reward_account': reward_account,
        'earning_methods': earning_methods,
    }
    
    return render(request, 'rewards/earn_points.html', context)


# Helper Functions

def get_tier_benefits(tier):
    """Get benefits for a specific tier."""
    benefits = {
        'bronze': [
            'Earn 1 point per EGP spent',
            'Basic customer support',
            'Birthday rewards',
        ],
        'silver': [
            'Earn 1.5 points per EGP spent',
            'Priority customer support',
            '5% exclusive discounts',
            'Early product access',
        ],
        'gold': [
            'Earn 2 points per EGP spent',
            'Free shipping',
            '10% exclusive discounts',
            'VIP support',
        ],
        'platinum': [
            'Earn 3 points per EGP spent',
            'Personal shopping assistant',
            '15% exclusive discounts',
            'VIP events access',
            'Priority everything',
        ],
    }
    return benefits.get(tier, benefits['bronze'])


# AJAX Endpoints

@login_required
def get_points_balance(request):
    """
    AJAX endpoint to get current points balance.
    """
    try:
        reward_account = RewardAccount.objects.get(user=request.user)
        return JsonResponse({
            'success': True,
            'points_balance': reward_account.points_balance,
            'tier': reward_account.tier,
            'total_earned': reward_account.total_earned,
        })
    except RewardAccount.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Reward account not found'
        }, status=404)


@login_required
def quick_redeem(request):
    """
    AJAX endpoint for quick redemption (e.g., apply points to cart).
    """
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        points_to_redeem = int(data.get('points', 0))
        
        try:
            reward_account = RewardAccount.objects.get(user=request.user)
            
            if reward_account.points_balance < points_to_redeem:
                return JsonResponse({
                    'success': False,
                    'error': 'Insufficient points'
                }, status=400)
            
            # Calculate discount amount (1 point = 0.01 EGP)
            discount_amount = Decimal(points_to_redeem) * Decimal('0.01')
            
            # Store in session for checkout
            request.session['rewards_redemption'] = {
                'points': points_to_redeem,
                'discount': float(discount_amount),
            }
            
            return JsonResponse({
                'success': True,
                'points_redeemed': points_to_redeem,
                'discount_amount': float(discount_amount),
                'new_balance': reward_account.points_balance,
            })
            
        except RewardAccount.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Reward account not found'
            }, status=404)
    
    return JsonResponse({'success': False, 'error': 'Invalid request'}, status=400)


# Helper Functions

def generate_coupon_code(user, reward):
    """
    Generate a unique coupon code for reward redemption.
    Integrates with the coupon system.
    """
    import uuid
    import string
    import random
    from django.utils import timezone
    from datetime import timedelta
    
    # Generate random code
    code_prefix = 'REWARD'
    code_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    coupon_code = f'{code_prefix}{code_suffix}'
    
    # Try to create coupon in the coupon system
    try:
        from apps.orders.coupon_models import Coupon
        
        # Calculate expiry (30 days from now)
        expires_at = timezone.now() + timedelta(days=30)
        
        # Create coupon
        coupon = Coupon.objects.create(
            code=coupon_code,
            discount_type='fixed',
            discount_value=reward.discount_amount,
            min_order_value=0,
            max_uses=1,
            max_uses_per_user=1,
            valid_from=timezone.now(),
            valid_to=expires_at,
            is_active=True,
            description=f'Reward redemption: {reward.name}',
        )
        
        # Link coupon to user so they can use it
        coupon.allowed_users.add(user)
        
        return coupon_code
        
    except ImportError:
        # Coupon model not available, return code anyway
        return coupon_code
    except Exception as e:
        print(f"Error creating coupon: {e}")
        return coupon_code


def create_notification(user, notification_type, title, message, link='', metadata=None):
    """
    Create an in-app notification for a user.
    """
    try:
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
            metadata=metadata or {}
        )
        return notification
    except Exception as e:
        print(f"Error creating notification: {e}")
        return None


def send_redemption_email(user, reward, redemption, coupon_code=''):
    """
    Send email notification for reward redemption.
    """
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    
    try:
        subject = f'Reward Redeemed: {reward.name}'
        
        context = {
            'user': user,
            'reward': reward,
            'redemption': redemption,
            'coupon_code': coupon_code,
        }
        
        # Render email templates
        html_message = render_to_string('emails/reward_redeemed.html', context)
        plain_message = render_to_string('emails/reward_redeemed.txt', context)
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
        
        return True
    except Exception as e:
        print(f"Error sending redemption email: {e}")
        return False


def send_points_earned_email(user, points, order=None):
    """
    Send email notification when points are earned.
    """
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    
    try:
        subject = f'You earned {points} reward points!'
        
        from django.conf import settings
        context = {
            'user': user,
            'points': points,
            'order': order,
            'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
        }
        
        html_message = render_to_string('emails/points_earned.html', context)
        plain_message = render_to_string('emails/points_earned.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
        
        return True
    except Exception as e:
        print(f"Error sending points earned email: {e}")
        return False


def send_tier_upgrade_email(user, old_tier, new_tier):
    """
    Send email notification when user's tier is upgraded.
    """
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.conf import settings
    
    try:
        subject = f'Congratulations! You\'ve reached {new_tier.title()} Tier!'
        
        context = {
            'user': user,
            'old_tier': old_tier,
            'new_tier': new_tier,
        }
        
        html_message = render_to_string('emails/tier_upgrade.html', context)
        plain_message = render_to_string('emails/tier_upgrade.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
        
        # Also create notification
        create_notification(
            user=user,
            notification_type='tier_upgrade',
            title=f'Tier Upgraded to {new_tier.title()}!',
            message=f'Congratulations! You\'ve been upgraded from {old_tier.title()} to {new_tier.title()} tier.',
            link='/rewards/tiers/'
        )
        
        return True
    except Exception as e:
        print(f"Error sending tier upgrade email: {e}")
        return False


def check_and_award_daily_login(user):
    """
    Check and award daily login reward.
    Called from middleware or login signal.
    """
    from datetime import date, timedelta
    from .models import DailyLoginReward
    
    try:
        today = date.today()
        
        # Check if already logged in today
        if DailyLoginReward.objects.filter(user=user, login_date=today).exists():
            return None
        
        # Get yesterday's login
        yesterday = today - timedelta(days=1)
        yesterday_login = DailyLoginReward.objects.filter(
            user=user, 
            login_date=yesterday
        ).first()
        
        # Calculate streak
        if yesterday_login:
            streak_day = yesterday_login.streak_day + 1
        else:
            streak_day = 1
        
        # Calculate points based on streak (bonus for streaks)
        base_points = 10
        bonus_points = (streak_day - 1) * 5 if streak_day <= 7 else 30
        total_points = base_points + bonus_points
        
        # Create daily login record
        daily_login = DailyLoginReward.objects.create(
            user=user,
            login_date=today,
            points_earned=total_points,
            streak_day=streak_day
        )
        
        # Award points
        reward_account, _ = RewardAccount.objects.get_or_create(
            user=user,
            defaults={'points_balance': 0}
        )
        
        reward_account.add_points(
            amount=total_points,
            transaction_type='bonus',
            description=f'Daily login reward (Day {streak_day})'
        )
        
        # Create notification
        create_notification(
            user=user,
            notification_type='points_earned',
            title='Daily Login Reward!',
            message=f'You earned {total_points} points for logging in today! (Streak: {streak_day} days)',
            link='/rewards/'
        )
        
        return daily_login
        
    except Exception as e:
        print(f"Error awarding daily login: {e}")
        return None


# Additional Views for New Features

@login_required
def notifications_center(request):
    """
    Display user's notifications with mark as read functionality.
    """
    return redirect('notifications:center')


@login_required
def mark_all_notifications_read(request):
    """
    Mark all notifications as read.
    """
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        messages.success(request, 'All notifications marked as read.')
    return redirect('notifications:center')


@login_required
def gift_points_view(request):
    """
    View for gifting points to another user.
    """
    from django.contrib.auth import get_user_model
    from .models import PointsGift
    
    User = get_user_model()
    
    # Get reward account
    try:
        reward_account = RewardAccount.objects.get(user=request.user)
    except RewardAccount.DoesNotExist:
        messages.error(request, 'Reward account not found.')
        return redirect('rewards:dashboard')
    
    if request.method == 'POST':
        recipient_email = request.POST.get('recipient_email')
        amount = int(request.POST.get('amount', 0))
        message = request.POST.get('message', '')
        
        # Validation
        if amount <= 0:
            messages.error(request, 'Please enter a valid amount.')
            return redirect('rewards:gift_points')
        
        if amount > reward_account.points_balance:
            messages.error(request, f'Insufficient points. You only have {reward_account.points_balance} points.')
            return redirect('rewards:gift_points')
        
        # Get recipient
        try:
            recipient = User.objects.get(email=recipient_email)
        except User.DoesNotExist:
            messages.error(request, 'Recipient not found. Please check the email address.')
            return redirect('rewards:gift_points')
        
        if recipient == request.user:
            messages.error(request, 'You cannot gift points to yourself.')
            return redirect('rewards:gift_points')
        
        # Create gift
        gift = PointsGift.objects.create(
            sender=request.user,
            recipient=recipient,
            amount=amount,
            message=message,
            status='pending'
        )
        
        # Process gift immediately (or require admin approval)
        if gift.process():
            messages.success(
                request, 
                f'Successfully gifted {amount} points to {recipient.email}!'
            )
            
            # Notify recipient
            create_notification(
                user=recipient,
                notification_type='points_gift_received',
                title='You Received a Gift!',
                message=f'{request.user.email} sent you {amount} points!',
                link='/rewards/',
                metadata={'gift_id': gift.id, 'sender': request.user.email}
            )
        else:
            messages.error(request, 'Failed to process gift. Please try again.')
        
        return redirect('rewards:dashboard')
    
    # GET request - show form
    context = {
        'reward_account': reward_account,
    }
    
    return render(request, 'rewards/gift_points.html', context)


@login_required
def gift_history(request):
    """
    View user's gift history (sent and received).
    """
    from .models import PointsGift
    
    gifts_sent = PointsGift.objects.filter(sender=request.user).order_by('-created_at')
    gifts_received = PointsGift.objects.filter(recipient=request.user).order_by('-created_at')
    
    context = {
        'gifts_sent': gifts_sent[:10],
        'gifts_received': gifts_received[:10],
    }
    
    return render(request, 'rewards/gift_history.html', context)

