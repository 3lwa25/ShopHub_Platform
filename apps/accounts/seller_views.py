"""
Seller Dashboard Views
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import models
from django.db.models import Sum, Count, Q, Avg, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from apps.products.models import Product
from apps.orders.models import Order, OrderItem, ShipmentTracking
from .decorators import approved_seller_required


@approved_seller_required
def seller_dashboard(request):
    """
    Main seller dashboard with overview statistics
    """
    seller_profile = request.user.seller_profile
    
    # Date ranges
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    last_7_days = today - timedelta(days=7)
    
    # Get seller's products
    products = Product.objects.filter(seller=seller_profile)
    total_products = products.count()
    active_products = products.filter(status='active').count()
    out_of_stock = products.filter(stock=0).count()
    
    # Seller-specific orders (orders that contain items belonging to this seller)
    seller_orders = Order.objects.filter(items__seller=seller_profile).distinct()
    seller_order_items = OrderItem.objects.filter(seller=seller_profile).select_related('order', 'product')
    
    # Order statistics
    # Pending orders: Orders waiting for seller action (payment received or COD selected, ready to process/ship)
    # - CREATED: Order just created, waiting for payment
    # - PENDING_PAYMENT: Payment not yet completed (COD or online payment pending)
    # - PAID: Payment completed, waiting for seller to process/ship
    pending_orders = seller_orders.filter(status__in=['CREATED', 'PENDING_PAYMENT', 'PAID']).count()
    processing_orders = seller_orders.filter(status='PROCESSING').count()
    shipped_orders = seller_orders.filter(status__in=['SHIPPED', 'OUT_FOR_DELIVERY']).count()
    delivered_orders = seller_orders.filter(status='DELIVERED').count()
    
    # Revenue statistics
    revenue_expression = ExpressionWrapper(
        F('unit_price') * F('quantity'),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )

    total_revenue = seller_order_items.filter(
        order__status='DELIVERED',
        order__payment_status='completed'
    ).aggregate(total=Sum(revenue_expression))['total'] or 0
    
    revenue_last_30_days = seller_order_items.filter(
        order__status='DELIVERED',
        order__payment_status='completed',
        order__updated_at__date__gte=last_30_days
    ).aggregate(total=Sum(revenue_expression))['total'] or 0
    
    revenue_last_7_days = seller_order_items.filter(
        order__status='DELIVERED',
        order__payment_status='completed',
        order__updated_at__date__gte=last_7_days
    ).aggregate(total=Sum(revenue_expression))['total'] or 0
    
    # Recent orders (last 10)
    recent_orders = seller_orders.select_related('buyer').order_by('-created_at')[:10]
    
    # Top selling products
    top_products = Product.objects.filter(seller=seller_profile).annotate(
        total_sold=Count('order_items', filter=Q(order_items__order__status='DELIVERED'))
    ).order_by('-total_sold')[:5]
    
    # Low stock alerts
    low_stock_products = products.filter(
        stock__lte=F('low_stock_threshold'),
        status='active'
    ).order_by('stock')[:10]
    
    context = {
        'seller_profile': seller_profile,
        'total_products': total_products,
        'active_products': active_products,
        'out_of_stock': out_of_stock,
        'pending_orders': pending_orders,
        'processing_orders': processing_orders,
        'shipped_orders': shipped_orders,
        'delivered_orders': delivered_orders,
        'total_revenue': total_revenue,
        'revenue_last_30_days': revenue_last_30_days,
        'revenue_last_7_days': revenue_last_7_days,
        'recent_orders': recent_orders,
        'top_products': top_products,
        'low_stock_products': low_stock_products,
    }
    
    return render(request, 'seller/dashboard.html', context)


def seller_pending(request):
    """
    Page shown to sellers awaiting approval
    """
    if not request.user.is_authenticated or not request.user.is_seller:
        return redirect('core:home')
    
    try:
        seller_profile = request.user.seller_profile
        if seller_profile.is_approved:
            return redirect('seller:dashboard')
    except AttributeError:
        messages.error(request, 'Seller profile not found.')
        return redirect('core:home')
    
    context = {
        'seller_profile': seller_profile,
    }
    return render(request, 'seller/pending_approval.html', context)


@approved_seller_required
def seller_analytics(request):
    """
    Detailed analytics dashboard for sellers
    """
    seller_profile = request.user.seller_profile
    
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    
    seller_orders = Order.objects.filter(items__seller=seller_profile).distinct()
    seller_order_items = OrderItem.objects.filter(seller=seller_profile).select_related('order', 'product', 'product__category')
    
    revenue_expression = ExpressionWrapper(
        F('unit_price') * F('quantity'),
        output_field=DecimalField(max_digits=12, decimal_places=2)
    )
    
    # Revenue over time (last 30 days, grouped by day)
    daily_revenue = seller_order_items.filter(
        order__created_at__date__gte=last_30_days,
        order__status='DELIVERED'
    ).annotate(
        day=TruncDate('order__created_at')
    ).values('day').annotate(
        revenue=Sum(revenue_expression),
        order_count=Count('order', distinct=True)
    ).order_by('day')
    
    # Product performance
    product_performance = seller_order_items.filter(
        order__status='DELIVERED'
    ).values(
        'product__id',
        'product__title',
        'product__sku'
    ).annotate(
        units_sold=Sum('quantity'),
        revenue=Sum(revenue_expression)
    ).order_by('-revenue')[:20]
    
    # Category breakdown
    category_stats = seller_order_items.filter(
        order__status='DELIVERED'
    ).values('product__category__name').annotate(
        total_revenue=Sum(revenue_expression),
        units_sold=Sum('quantity')
    ).order_by('-total_revenue')
    
    # Customer insights
    top_customers = seller_order_items.filter(
        order__status='DELIVERED'
    ).values(
        'order__buyer__email',
        'order__buyer__full_name'
    ).annotate(
        total_orders=Count('order', distinct=True),
        total_spent=Sum(revenue_expression)
    ).order_by('-total_spent')[:10]
    
    # Order fulfillment metrics
    avg_processing_time_raw = seller_orders.filter(
        status__in=['SHIPPED', 'OUT_FOR_DELIVERY', 'DELIVERED'],
        updated_at__isnull=False
    ).annotate(
        processing_time=F('updated_at') - F('created_at')
    ).aggregate(avg=Avg('processing_time'))
    
    # Convert timedelta to human-readable format
    avg_processing_time = None
    if avg_processing_time_raw.get('avg'):
        total_seconds = avg_processing_time_raw['avg'].total_seconds()
        days = int(total_seconds // 86400)
        hours = int((total_seconds % 86400) // 3600)
        minutes = int((total_seconds % 3600) // 60)
        
        if days > 0:
            avg_processing_time = f"{days} day{'s' if days != 1 else ''}, {hours} hour{'s' if hours != 1 else ''}"
        elif hours > 0:
            avg_processing_time = f"{hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
        else:
            avg_processing_time = f"{minutes} minute{'s' if minutes != 1 else ''}"
    
    context = {
        'seller_profile': seller_profile,
        'daily_revenue': list(daily_revenue),
        'product_performance': product_performance,
        'category_stats': category_stats,
        'top_customers': top_customers,
        'avg_processing_time': avg_processing_time,
    }
    
    return render(request, 'seller/analytics.html', context)

