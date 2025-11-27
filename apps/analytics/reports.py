"""
Sales Reports and Analytics
"""
from django.db.models import Count, Sum, Avg, F, Q, DecimalField
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal
import csv
from io import StringIO

from apps.orders.models import Order, OrderItem
from apps.products.models import Product
from apps.accounts.models import User


class SalesReports:
    """
    Generate various sales reports
    """
    
    @staticmethod
    def generate_daily_sales_report(start_date=None, end_date=None):
        """
        Generate daily sales report
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        daily_sales = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
            status__in=['delivered', 'shipped']
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            total_orders=Count('id'),
            total_revenue=Sum('total_amount'),
            avg_order_value=Avg('total_amount')
        ).order_by('date')
        
        return list(daily_sales)
    
    @staticmethod
    def generate_monthly_sales_report(year=None):
        """
        Generate monthly sales report for a given year
        """
        if not year:
            year = timezone.now().year
        
        start_date = datetime(year, 1, 1)
        end_date = datetime(year, 12, 31, 23, 59, 59)
        
        monthly_sales = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
            status__in=['delivered', 'shipped']
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total_orders=Count('id'),
            total_revenue=Sum('total_amount'),
            avg_order_value=Avg('total_amount')
        ).order_by('month')
        
        return list(monthly_sales)
    
    @staticmethod
    def generate_product_performance_report(limit=50):
        """
        Generate product performance report
        """
        products = Product.objects.annotate(
            units_sold=Count('order_items', filter=Q(order_items__order__status__in=['delivered', 'shipped'])),
            revenue=Sum('order_items__price', filter=Q(order_items__order__status__in=['delivered', 'shipped'])),
            avg_rating=Avg('reviews__rating')
        ).filter(units_sold__gt=0).order_by('-revenue')[:limit]
        
        return products
    
    @staticmethod
    def generate_category_performance_report():
        """
        Generate category performance report
        """
        from apps.products.models import Category
        
        categories = Category.objects.annotate(
            total_products=Count('products', filter=Q(products__status='active')),
            units_sold=Count(
                'products__order_items',
                filter=Q(products__order_items__order__status__in=['delivered', 'shipped'])
            ),
            revenue=Sum(
                'products__order_items__price',
                filter=Q(products__order_items__order__status__in=['delivered', 'shipped'])
            )
        ).filter(units_sold__gt=0).order_by('-revenue')
        
        return categories
    
    @staticmethod
    def generate_seller_performance_report(limit=50):
        """
        Generate seller performance report
        """
        sellers = User.objects.filter(role='seller').annotate(
            total_products=Count('products', filter=Q(products__status='active')),
            units_sold=Count(
                'products__order_items',
                filter=Q(products__order_items__order__status__in=['delivered', 'shipped'])
            ),
            revenue=Sum(
                'products__order_items__price',
                filter=Q(products__order_items__order__status__in=['delivered', 'shipped'])
            ),
            avg_rating=Avg('products__reviews__rating')
        ).filter(units_sold__gt=0).order_by('-revenue')[:limit]
        
        return sellers
    
    @staticmethod
    def generate_customer_report(limit=100):
        """
        Generate customer report with purchase history
        """
        customers = User.objects.filter(role='buyer').annotate(
            total_orders=Count('orders', filter=Q(orders__status__in=['delivered', 'shipped'])),
            total_spent=Sum('orders__total_amount', filter=Q(orders__status__in=['delivered', 'shipped'])),
            avg_order_value=Avg('orders__total_amount', filter=Q(orders__status__in=['delivered', 'shipped'])),
            last_order_date=Max('orders__created_at')
        ).filter(total_orders__gt=0).order_by('-total_spent')[:limit]
        
        return customers
    
    @staticmethod
    def generate_revenue_summary(start_date=None, end_date=None):
        """
        Generate revenue summary report
        """
        if not start_date:
            start_date = timezone.now() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now()
        
        orders = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date,
            status__in=['delivered', 'shipped']
        )
        
        summary = orders.aggregate(
            total_orders=Count('id'),
            total_revenue=Sum('total_amount'),
            avg_order_value=Avg('total_amount'),
            min_order_value=Min('total_amount'),
            max_order_value=Max('total_amount')
        )
        
        # Calculate revenue by status
        revenue_by_status = Order.objects.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        ).values('status').annotate(
            count=Count('id'),
            revenue=Sum('total_amount')
        ).order_by('-revenue')
        
        summary['by_status'] = list(revenue_by_status)
        
        return summary
    
    @staticmethod
    def export_to_csv(report_data, fields):
        """
        Export report data to CSV
        """
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        
        for row in report_data:
            writer.writerow({field: row.get(field, '') for field in fields})
        
        return output.getvalue()
    
    @staticmethod
    def generate_inventory_report():
        """
        Generate inventory status report
        """
        from django.db.models import Case, When, Value, CharField
        
        products = Product.objects.annotate(
            stock_status=Case(
                When(stock=0, then=Value('Out of Stock')),
                When(stock__lte=F('low_stock_threshold'), then=Value('Low Stock')),
                default=Value('In Stock'),
                output_field=CharField()
            )
        ).values('stock_status').annotate(
            count=Count('id')
        )
        
        return list(products)
    
    @staticmethod
    def generate_low_stock_report():
        """
        Generate low stock products report
        """
        low_stock_products = Product.objects.filter(
            status='active'
        ).filter(
            Q(stock=0) | Q(stock__lte=F('low_stock_threshold'))
        ).select_related('category', 'seller').order_by('stock')
        
        return low_stock_products


class AnalyticsReports:
    """
    Generate analytics and metrics reports
    """
    
    @staticmethod
    def generate_conversion_funnel():
        """
        Generate conversion funnel report
        """
        from apps.analytics.models import Event
        
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        
        events = Event.objects.filter(created_at__gte=last_30_days)
        
        funnel = {
            'product_views': events.filter(event_type='view_product').count(),
            'add_to_cart': events.filter(event_type='add_to_cart').count(),
            'purchases': events.filter(event_type='purchase').count(),
        }
        
        # Calculate conversion rates
        if funnel['product_views'] > 0:
            funnel['cart_conversion_rate'] = (funnel['add_to_cart'] / funnel['product_views']) * 100
            funnel['purchase_conversion_rate'] = (funnel['purchases'] / funnel['product_views']) * 100
        else:
            funnel['cart_conversion_rate'] = 0
            funnel['purchase_conversion_rate'] = 0
        
        if funnel['add_to_cart'] > 0:
            funnel['checkout_conversion_rate'] = (funnel['purchases'] / funnel['add_to_cart']) * 100
        else:
            funnel['checkout_conversion_rate'] = 0
        
        return funnel
    
    @staticmethod
    def generate_user_engagement_report():
        """
        Generate user engagement report
        """
        from apps.analytics.models import Event
        
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        
        # Active users
        active_users = Event.objects.filter(
            created_at__gte=last_30_days
        ).values('user_id').distinct().count()
        
        # Sessions
        total_sessions = Event.objects.filter(
            created_at__gte=last_30_days
        ).values('session_id').distinct().count()
        
        # Events per user
        events_per_user = Event.objects.filter(
            created_at__gte=last_30_days,
            user_id__isnull=False
        ).values('user_id').annotate(
            event_count=Count('id')
        ).aggregate(avg=Avg('event_count'))
        
        return {
            'active_users': active_users,
            'total_sessions': total_sessions,
            'avg_events_per_user': events_per_user['avg'] or 0
        }
    
    @staticmethod
    def generate_trending_products_report(days=7, limit=20):
        """
        Generate trending products report
        """
        from apps.analytics.models import Event
        
        since = timezone.now() - timedelta(days=days)
        
        trending = Event.objects.filter(
            event_type='view_product',
            created_at__gte=since,
            product_id__isnull=False
        ).values('product_id').annotate(
            view_count=Count('id')
        ).order_by('-view_count')[:limit]
        
        product_ids = [item['product_id'] for item in trending]
        products = Product.objects.filter(id__in=product_ids)
        
        # Create a mapping
        product_map = {p.id: p for p in products}
        
        result = []
        for item in trending:
            product = product_map.get(item['product_id'])
            if product:
                result.append({
                    'product': product,
                    'view_count': item['view_count']
                })
        
        return result


# Import for aggregate functions
from django.db.models import Max, Min

