"""
System Monitoring and Health Checks
"""
import psutil
import time
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from datetime import datetime, timedelta
from decimal import Decimal


class SystemMonitor:
    """
    Monitor system resources and health
    """
    
    @staticmethod
    def get_system_stats():
        """
        Get system resource usage statistics
        """
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'timestamp': datetime.now().isoformat()
        }
    
    @staticmethod
    def get_database_stats():
        """
        Get database statistics
        """
        from django.db import connections
        
        stats = {}
        for conn_name in connections:
            conn = connections[conn_name]
            with conn.cursor() as cursor:
                # Get database size (PostgreSQL specific, adapt for other DBs)
                try:
                    cursor.execute("SELECT pg_database_size(current_database())")
                    size = cursor.fetchone()[0]
                    stats[conn_name] = {
                        'size_mb': size / (1024 * 1024),
                        'status': 'connected'
                    }
                except Exception as e:
                    stats[conn_name] = {
                        'status': 'error',
                        'error': str(e)
                    }
        
        return stats
    
    @staticmethod
    def check_database_connection():
        """
        Check if database connection is working
        """
        try:
            from django.db import connection
            connection.ensure_connection()
            return True, 'Database connection OK'
        except Exception as e:
            return False, f'Database connection failed: {str(e)}'
    
    @staticmethod
    def check_cache():
        """
        Check if cache is working
        """
        try:
            test_key = 'health_check_test'
            test_value = 'test_value'
            cache.set(test_key, test_value, 10)
            retrieved = cache.get(test_key)
            cache.delete(test_key)
            
            if retrieved == test_value:
                return True, 'Cache OK'
            else:
                return False, 'Cache not working correctly'
        except Exception as e:
            return False, f'Cache check failed: {str(e)}'
    
    @staticmethod
    def get_application_stats():
        """
        Get application-specific statistics
        """
        from apps.products.models import Product
        from apps.orders.models import Order
        from apps.accounts.models import User
        from apps.reviews.models import Review
        
        return {
            'total_products': Product.objects.count(),
            'active_products': Product.objects.filter(status='active').count(),
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'total_orders': Order.objects.count(),
            'pending_orders': Order.objects.filter(status='pending').count(),
            'total_reviews': Review.objects.count(),
        }
    
    @staticmethod
    def health_check():
        """
        Comprehensive health check
        """
        health = {
            'status': 'healthy',
            'checks': {},
            'timestamp': datetime.now().isoformat()
        }
        
        # Check database
        db_ok, db_msg = SystemMonitor.check_database_connection()
        health['checks']['database'] = {
            'status': 'ok' if db_ok else 'error',
            'message': db_msg
        }
        if not db_ok:
            health['status'] = 'unhealthy'
        
        # Check cache
        cache_ok, cache_msg = SystemMonitor.check_cache()
        health['checks']['cache'] = {
            'status': 'ok' if cache_ok else 'warning',
            'message': cache_msg
        }
        
        # Check system resources
        system_stats = SystemMonitor.get_system_stats()
        health['checks']['system'] = {
            'status': 'ok' if system_stats['cpu_percent'] < 80 else 'warning',
            'cpu_percent': system_stats['cpu_percent'],
            'memory_percent': system_stats['memory_percent'],
            'disk_percent': system_stats['disk_percent']
        }
        
        return health


class PerformanceMetrics:
    """
    Track and analyze performance metrics
    """
    
    @staticmethod
    def get_slow_queries(threshold_ms=100):
        """
        Get slow database queries (requires query logging)
        """
        # This would typically query a performance log table
        # For now, return placeholder
        return []
    
    @staticmethod
    def get_endpoint_metrics(hours=24):
        """
        Get API endpoint performance metrics
        """
        # This would typically query performance logs
        # For now, return placeholder
        return {}
    
    @staticmethod
    def get_error_rate(hours=24):
        """
        Calculate error rate for the last N hours
        """
        # This would typically query error logs
        # For now, return placeholder
        return {
            'total_requests': 0,
            'error_count': 0,
            'error_rate': 0.0
        }


class AlertManager:
    """
    Manage system alerts and notifications
    """
    
    @staticmethod
    def check_thresholds():
        """
        Check if any metrics exceed thresholds
        """
        alerts = []
        
        # Check system resources
        system_stats = SystemMonitor.get_system_stats()
        if system_stats['cpu_percent'] > 80:
            alerts.append({
                'level': 'warning',
                'message': f"High CPU usage: {system_stats['cpu_percent']}%",
                'timestamp': datetime.now()
            })
        
        if system_stats['memory_percent'] > 85:
            alerts.append({
                'level': 'warning',
                'message': f"High memory usage: {system_stats['memory_percent']}%",
                'timestamp': datetime.now()
            })
        
        if system_stats['disk_percent'] > 90:
            alerts.append({
                'level': 'critical',
                'message': f"High disk usage: {system_stats['disk_percent']}%",
                'timestamp': datetime.now()
            })
        
        # Check pending orders
        from apps.orders.models import Order
        old_pending_orders = Order.objects.filter(
            status='pending',
            created_at__lt=datetime.now() - timedelta(days=3)
        ).count()
        
        if old_pending_orders > 0:
            alerts.append({
                'level': 'warning',
                'message': f"{old_pending_orders} orders pending for more than 3 days",
                'timestamp': datetime.now()
            })
        
        # Check low stock products
        from apps.products.models import Product
        from django.db.models import F
        
        low_stock = Product.objects.filter(
            status='active',
            stock__lte=F('low_stock_threshold'),
            stock__gt=0
        ).count()
        
        if low_stock > 0:
            alerts.append({
                'level': 'info',
                'message': f"{low_stock} products are low on stock",
                'timestamp': datetime.now()
            })
        
        out_of_stock = Product.objects.filter(
            status='active',
            stock=0
        ).count()
        
        if out_of_stock > 0:
            alerts.append({
                'level': 'warning',
                'message': f"{out_of_stock} products are out of stock",
                'timestamp': datetime.now()
            })
        
        return alerts
    
    @staticmethod
    def send_alert(alert):
        """
        Send alert notification (email, SMS, etc.)
        """
        # Implement alert notification logic
        # For now, just log it
        from apps.common.logging_config import app_logger
        
        level_map = {
            'info': app_logger.info,
            'warning': app_logger.warning,
            'critical': app_logger.critical
        }
        
        log_func = level_map.get(alert['level'], app_logger.info)
        log_func(f"ALERT: {alert['message']}")


# Export monitoring utilities
__all__ = [
    'SystemMonitor',
    'PerformanceMetrics',
    'AlertManager'
]

