"""
Notification Views
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Count
from django.utils import timezone

from .models import Notification


FILTER_CATALOG = {
    'all': {'label': 'All Alerts', 'icon': 'list-ul', 'types': None},
    'orders': {'label': 'Orders & Shipping', 'icon': 'box', 'types': ['order', 'shipment']},
    'payments': {'label': 'Payments', 'icon': 'credit-card', 'types': ['payment']},
    'rewards': {'label': 'Rewards & Promos', 'icon': 'trophy', 'types': ['reward', 'promotion', 'points_earned', 'tier_upgrade']},
    'system': {'label': 'System', 'icon': 'shield-alt', 'types': ['system']},
    'products': {'label': 'Catalog & Reviews', 'icon': 'tags', 'types': ['product', 'review']},
}

ROLE_FILTER_KEYS = {
    'buyer': ['orders', 'payments', 'rewards', 'system'],
    'seller': ['orders', 'payments', 'products', 'system'],
    'admin': ['orders', 'payments', 'products', 'system', 'rewards'],
}

ROLE_HERO = {
    'buyer': {
        'badge': 'Buyer feed',
        'title': 'All of your ShopHub updates in one place',
        'description': 'Track deliveries, payment approvals, rewards, and promotions without digging through emails.',
    },
    'seller': {
        'badge': 'Seller feed',
        'title': 'Stay ahead of orders, payouts, and catalog reviews',
        'description': 'Monitor order actions, buyer messages, and payout approvals to keep fulfillment on track.',
    },
    'admin': {
        'badge': 'Admin feed',
        'title': 'Platform-wide alerts and escalations',
        'description': 'Follow payment escalations, review queues, and system wide announcements in real time.',
    },
}

TYPE_ICONS = {
    'order': 'shopping-bag',
    'shipment': 'truck',
    'payment': 'credit-card',
    'reward': 'trophy',
    'promotion': 'gift',
    'system': 'shield-alt',
    'product': 'tags',
    'review': 'star',
    'points_earned': 'coins',
    'tier_upgrade': 'medal',
}


@login_required
def notification_center(request):
    """
    Display tailored notifications for the current user with role-aware filters.
    """
    role = 'buyer'
    if getattr(request.user, 'is_seller', False):
        role = 'seller'
    if getattr(request.user, 'is_admin_user', False):
        role = 'admin'

    scope = request.GET.get('scope', 'all')
    def build_filter(key):
        data = FILTER_CATALOG[key].copy()
        data['key'] = key
        return data

    available_filters = [build_filter('all')]
    for key in ROLE_FILTER_KEYS.get(role, []):
        available_filters.append(build_filter(key))

    valid_keys = [f['key'] for f in available_filters]
    if scope not in valid_keys:
        scope = 'all'
    active_filter = next(f for f in available_filters if f['key'] == scope)

    notifications_qs = Notification.objects.filter(user=request.user).order_by('-created_at')
    if active_filter['types']:
        notifications_qs = notifications_qs.filter(notification_type__in=active_filter['types'])

    paginator = Paginator(notifications_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    for note in page_obj.object_list:
        note.icon_name = TYPE_ICONS.get(note.notification_type, 'bell')

    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    type_totals = Notification.objects.filter(user=request.user).values('notification_type').annotate(total=Count('id'))
    totals_map = {row['notification_type']: row['total'] for row in type_totals}

    def filter_count(filter_def):
        if not filter_def['types']:
            return sum(totals_map.values())
        return sum(totals_map.get(t, 0) for t in filter_def['types'])

    for option in available_filters:
        option['count'] = filter_count(option)

    context = {
        'page_obj': page_obj,
        'unread_count': unread_count,
        'hero': ROLE_HERO[role],
        'filter_options': available_filters,
        'active_scope': scope,
    }
    return render(request, 'notifications/notification_center.html', context)


@login_required
@require_POST
def mark_as_read(request, notification_id):
    """
    Mark a notification as read
    """
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=['is_read', 'read_at'])
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def mark_all_as_read(request):
    """
    Mark all notifications as read
    """
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
    return JsonResponse({'success': True})


@login_required
def get_unread_count(request):
    """
    Get unread notification count (AJAX)
    """
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})

