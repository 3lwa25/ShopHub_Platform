"""
Custom Admin Dashboard with Analytics Widgets
"""
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from apps.products.models import Product
from apps.orders.models import Order
from apps.accounts.models import User
from apps.reviews.models import Review
from apps.analytics.models import Event


class AdminDashboard:
    """
    Custom admin dashboard with analytics widgets
    """
    
    @staticmethod
    def get_dashboard_stats():
        """
        Get key dashboard statistics
        """
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        last_7_days = now - timedelta(days=7)
        
        # Total counts
        total_products = Product.objects.filter(status='active').count()
        total_users = User.objects.filter(is_active=True).count()
        total_orders = Order.objects.count()
        total_reviews = Review.objects.count()
        
        # Revenue statistics
        total_revenue = Order.objects.filter(
            status__in=['delivered', 'shipped']
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        revenue_last_30_days = Order.objects.filter(
            status__in=['delivered', 'shipped'],
            created_at__gte=last_30_days
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        # Orders statistics
        pending_orders = Order.objects.filter(status='pending').count()
        processing_orders = Order.objects.filter(status='processing').count()
        shipped_orders = Order.objects.filter(status='shipped').count()
        delivered_orders = Order.objects.filter(status='delivered').count()
        
        # Recent statistics (last 7 days)
        new_users_last_week = User.objects.filter(date_joined__gte=last_7_days).count()
        new_orders_last_week = Order.objects.filter(created_at__gte=last_7_days).count()
        new_reviews_last_week = Review.objects.filter(created_at__gte=last_7_days).count()
        
        # Product statistics
        low_stock_products = Product.objects.filter(
            status='active',
            stock__lte=models.F('low_stock_threshold')
        ).count()
        
        out_of_stock_products = Product.objects.filter(
            status='active',
            stock=0
        ).count()
        
        # Average order value
        avg_order_value = Order.objects.filter(
            status__in=['delivered', 'shipped']
        ).aggregate(avg=Avg('total_amount'))['avg'] or Decimal('0.00')
        
        # Top selling products
        top_products = Product.objects.annotate(
            order_count=Count('order_items')
        ).order_by('-order_count')[:5]
        
        # Recent orders
        recent_orders = Order.objects.select_related('buyer').order_by('-created_at')[:10]
        
        # User statistics
        buyer_count = User.objects.filter(role='buyer').count()
        seller_count = User.objects.filter(role='seller').count()
        
        return {
            'total_products': total_products,
            'total_users': total_users,
            'total_orders': total_orders,
            'total_reviews': total_reviews,
            'total_revenue': total_revenue,
            'revenue_last_30_days': revenue_last_30_days,
            'pending_orders': pending_orders,
            'processing_orders': processing_orders,
            'shipped_orders': shipped_orders,
            'delivered_orders': delivered_orders,
            'new_users_last_week': new_users_last_week,
            'new_orders_last_week': new_orders_last_week,
            'new_reviews_last_week': new_reviews_last_week,
            'low_stock_products': low_stock_products,
            'out_of_stock_products': out_of_stock_products,
            'avg_order_value': avg_order_value,
            'top_products': top_products,
            'recent_orders': recent_orders,
            'buyer_count': buyer_count,
            'seller_count': seller_count,
        }
    
    @staticmethod
    def render_dashboard_widget(title, value, icon, color='primary', trend=None):
        """
        Render a dashboard widget
        """
        trend_html = ''
        if trend:
            trend_icon = 'fa-arrow-up' if trend > 0 else 'fa-arrow-down'
            trend_color = 'success' if trend > 0 else 'danger'
            trend_html = f'<span class="text-{trend_color}"><i class="fas {trend_icon}"></i> {abs(trend)}%</span>'
        
        return mark_safe(f'''
        <div class="card bg-{color} text-white mb-3">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="card-title mb-1">{title}</h6>
                        <h2 class="mb-0">{value}</h2>
                        {trend_html}
                    </div>
                    <div>
                        <i class="fas {icon} fa-3x opacity-50"></i>
                    </div>
                </div>
            </div>
        </div>
        ''')
    
    @staticmethod
    def render_chart_widget(title, data, chart_type='line'):
        """
        Render a chart widget
        """
        return mark_safe(f'''
        <div class="card mb-3">
            <div class="card-header">
                <h5 class="card-title mb-0">{title}</h5>
            </div>
            <div class="card-body">
                <canvas id="chart-{title.lower().replace(' ', '-')}" width="400" height="200"></canvas>
            </div>
        </div>
        <script>
            // Chart implementation would go here
            console.log('Chart data:', {data});
        </script>
        ''')
    
    @staticmethod
    def get_sales_data(days=30):
        """
        Get sales data for the last N days
        """
        now = timezone.now()
        start_date = now - timedelta(days=days)
        
        orders = Order.objects.filter(
            created_at__gte=start_date,
            status__in=['delivered', 'shipped']
        ).extra(
            select={'date': 'DATE(created_at)'}
        ).values('date').annotate(
            total_sales=Sum('total_amount'),
            order_count=Count('id')
        ).order_by('date')
        
        return list(orders)
    
    @staticmethod
    def get_category_distribution():
        """
        Get product distribution by category
        """
        from apps.products.models import Category
        
        categories = Category.objects.annotate(
            product_count=Count('products', filter=Q(products__status='active'))
        ).filter(product_count__gt=0).order_by('-product_count')[:10]
        
        return [{
            'name': cat.name,
            'count': cat.product_count
        } for cat in categories]
    
    @staticmethod
    def get_order_status_distribution():
        """
        Get order distribution by status
        """
        statuses = Order.objects.values('status').annotate(
            count=Count('id')
        ).order_by('-count')
        
        return list(statuses)
    
    @staticmethod
    def get_top_customers(limit=10):
        """
        Get top customers by order count and total spent
        """
        customers = User.objects.filter(
            role='buyer'
        ).annotate(
            order_count=Count('orders'),
            total_spent=Sum('orders__total_amount', filter=Q(orders__status__in=['delivered', 'shipped']))
        ).filter(order_count__gt=0).order_by('-total_spent')[:limit]
        
        return customers
    
    @staticmethod
    def get_top_sellers(limit=10):
        """
        Get top sellers by product count and revenue
        """
        sellers = User.objects.filter(
            role='seller'
        ).annotate(
            product_count=Count('products', filter=Q(products__status='active')),
            revenue=Sum('products__order_items__order__total_amount', 
                       filter=Q(products__order_items__order__status__in=['delivered', 'shipped']))
        ).filter(product_count__gt=0).order_by('-revenue')[:limit]
        
        return sellers
    
    @staticmethod
    def get_analytics_summary():
        """
        Get analytics summary from events
        """
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        
        events = Event.objects.filter(created_at__gte=last_30_days)
        
        summary = {
            'total_events': events.count(),
            'product_views': events.filter(event_type='view_product').count(),
            'add_to_cart': events.filter(event_type='add_to_cart').count(),
            'purchases': events.filter(event_type='purchase').count(),
            'tryon_sessions': events.filter(event_type='tryon').count(),
        }
        
        # Calculate conversion rates
        if summary['product_views'] > 0:
            summary['cart_conversion'] = (summary['add_to_cart'] / summary['product_views']) * 100
            summary['purchase_conversion'] = (summary['purchases'] / summary['product_views']) * 100
        else:
            summary['cart_conversion'] = 0
            summary['purchase_conversion'] = 0
        
        return summary


# Register custom admin site index
from django.contrib.admin import AdminSite
from django.http import HttpResponse
from django.template.response import TemplateResponse


class CustomAdminSite(AdminSite):
    """
    Custom admin site with enhanced dashboard
    """
    site_header = 'Shop Hub Administration'
    site_title = 'Shop Hub Admin'
    index_title = 'Dashboard'
    
    def index(self, request, extra_context=None):
        """
        Display custom dashboard with analytics
        """
        stats = AdminDashboard.get_dashboard_stats()
        analytics = AdminDashboard.get_analytics_summary()
        sales_data = AdminDashboard.get_sales_data(30)
        category_dist = AdminDashboard.get_category_distribution()
        order_status_dist = AdminDashboard.get_order_status_distribution()
        top_customers = AdminDashboard.get_top_customers(5)
        top_sellers = AdminDashboard.get_top_sellers(5)
        
        extra_context = extra_context or {}
        extra_context.update({
            'stats': stats,
            'analytics': analytics,
            'sales_data': sales_data,
            'category_dist': category_dist,
            'order_status_dist': order_status_dist,
            'top_customers': top_customers,
            'top_sellers': top_sellers,
        })
        
        return super().index(request, extra_context=extra_context)


# Create custom admin site instance
# custom_admin_site = CustomAdminSite(name='custom_admin')

