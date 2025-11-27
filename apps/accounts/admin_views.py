"""
Admin Dashboard Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from .decorators import admin_required
from .models import User, SellerProfile
from apps.products.models import Product, Category
from apps.orders.models import Order
from apps.reviews.models import Review
from apps.analytics.models import Event


@login_required
@admin_required
def admin_dashboard(request):
    """
    Admin dashboard with analytics and management options
    """
    # Get statistics
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    
    stats = {
        'total_users': User.objects.count(),
        'total_buyers': User.objects.filter(role='buyer').count(),
        'total_sellers': User.objects.filter(role='seller').count(),
        'total_admins': User.objects.filter(Q(role='admin') | Q(is_superuser=True)).count(),
        'new_users_today': User.objects.filter(created_at__date=now.date()).count(),
        'new_users_week': User.objects.filter(created_at__gte=now - timedelta(days=7)).count(),
        'total_products': Product.objects.count(),
        'active_products': Product.objects.filter(status='active').count(),
        'total_orders': Order.objects.count(),
        'pending_orders': Order.objects.filter(status='pending').count(),
        'total_revenue': Order.objects.filter(status__in=['delivered', 'shipped']).aggregate(
            total=Sum('total_amount'))['total'] or Decimal('0.00'),
        'revenue_30_days': Order.objects.filter(
            status__in=['delivered', 'shipped'],
            created_at__gte=last_30_days
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00'),
    }
    
    # Recent activity
    recent_users = User.objects.order_by('-created_at')[:10]
    recent_orders = Order.objects.select_related('buyer').order_by('-created_at')[:10]
    recent_products = Product.objects.select_related('seller', 'category').order_by('-created_at')[:10]
    
    # Pending approvals
    pending_sellers = SellerProfile.objects.filter(is_approved=False).select_related('user')[:10]
    
    context = {
        'stats': stats,
        'recent_users': recent_users,
        'recent_orders': recent_orders,
        'recent_products': recent_products,
        'pending_sellers': pending_sellers,
    }
    
    return render(request, 'accounts/admin_dashboard.html', context)


@login_required
@admin_required
def admin_users_list(request):
    """
    List all users with filtering options
    """
    role_filter = request.GET.get('role', '')
    search = request.GET.get('search', '')
    
    users = User.objects.all().order_by('-created_at')
    
    if role_filter:
        users = users.filter(role=role_filter)
    
    if search:
        users = users.filter(
            Q(email__icontains=search) |
            Q(username__icontains=search) |
            Q(full_name__icontains=search)
        )
    
    context = {
        'users': users,
        'role_filter': role_filter,
        'search': search,
    }
    
    return render(request, 'accounts/admin_users_list.html', context)


@login_required
@admin_required
def admin_user_edit(request, user_id):
    """
    Edit user details and permissions
    """
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        # Update user fields
        user.full_name = request.POST.get('full_name', user.full_name)
        user.email = request.POST.get('email', user.email)
        user.role = request.POST.get('role', user.role)
        user.is_active = request.POST.get('is_active') == 'on'
        user.verified = request.POST.get('verified') == 'on'
        user.is_staff = request.POST.get('is_staff') == 'on'
        
        user.save()
        messages.success(request, f'User {user.email} updated successfully!')
        return redirect('accounts:admin_users_list')
    
    context = {'user_obj': user}
    return render(request, 'accounts/admin_user_edit.html', context)


@login_required
@admin_required
def admin_products_manage(request):
    """
    Manage all products
    """
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    products = Product.objects.select_related('seller', 'category').order_by('-created_at')
    
    if status_filter:
        products = products.filter(status=status_filter)
    
    if search:
        products = products.filter(
            Q(title__icontains=search) |
            Q(sku__icontains=search) |
            Q(seller__email__icontains=search)
        )
    
    context = {
        'products': products,
        'status_filter': status_filter,
        'search': search,
    }
    
    return render(request, 'accounts/admin_products_manage.html', context)


@login_required
@admin_required
def admin_orders_manage(request):
    """
    Manage all orders
    """
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    orders = Order.objects.select_related('buyer').order_by('-created_at')
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search) |
            Q(buyer__email__icontains=search)
        )
    
    context = {
        'orders': orders,
        'status_filter': status_filter,
        'search': search,
    }
    
    return render(request, 'accounts/admin_orders_manage.html', context)


@login_required
@admin_required
def admin_approve_seller(request, seller_id):
    """
    Approve a seller account
    """
    seller_profile = get_object_or_404(SellerProfile, id=seller_id)
    
    if request.method == 'POST':
        seller_profile.is_approved = True
        seller_profile.save()
        messages.success(request, f'Seller {seller_profile.user.email} approved successfully!')
        return redirect('accounts:admin_dashboard')
    
    return redirect('accounts:admin_dashboard')

