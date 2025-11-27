"""
Search and Browsing History Models
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


class SearchQuery(models.Model):
    """Track user search queries for analytics and improvements"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_queries',
        help_text='User who performed the search (null for anonymous)'
    )
    session_key = models.CharField(
        max_length=40,
        blank=True,
        help_text='Session key for anonymous users'
    )
    query = models.CharField(
        max_length=255,
        db_index=True,
        help_text='Search query text'
    )
    results_count = models.IntegerField(
        default=0,
        help_text='Number of results found'
    )
    filters_applied = models.JSONField(
        default=dict,
        blank=True,
        help_text='Filters applied (price, category, etc.)'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'search_queries'
        verbose_name = 'Search Query'
        verbose_name_plural = 'Search Queries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['query', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.query} ({self.results_count} results)"
    
    @classmethod
    def popular_searches(cls, days=7, limit=10):
        """Get most popular searches in the last N days"""
        since = timezone.now() - timedelta(days=days)
        return cls.objects.filter(
            created_at__gte=since
        ).values('query').annotate(
            search_count=models.Count('id')
        ).order_by('-search_count')[:limit]


class BrowsingHistory(models.Model):
    """Track product views for recommendations"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='browsing_history'
    )
    session_key = models.CharField(
        max_length=40,
        blank=True,
        help_text='Session key for anonymous users'
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='view_history'
    )
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    duration = models.IntegerField(
        default=0,
        help_text='Time spent viewing in seconds'
    )
    referrer = models.CharField(
        max_length=255,
        blank=True,
        help_text='Where the user came from'
    )
    
    class Meta:
        db_table = 'browsing_history'
        verbose_name = 'Browsing History'
        verbose_name_plural = 'Browsing Histories'
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['user', '-viewed_at']),
            models.Index(fields=['session_key', '-viewed_at']),
            models.Index(fields=['product', '-viewed_at']),
        ]
    
    def __str__(self):
        user_str = self.user.email if self.user else self.session_key
        return f"{user_str} viewed {self.product.title}"
    
    @classmethod
    def recent_views(cls, user=None, session_key=None, limit=10):
        """Get recently viewed products"""
        if user:
            return cls.objects.filter(user=user).select_related('product')[:limit]
        elif session_key:
            return cls.objects.filter(session_key=session_key).select_related('product')[:limit]
        return cls.objects.none()
    
    @classmethod
    def trending_products(cls, days=7, limit=10):
        """Get most viewed products in recent days"""
        since = timezone.now() - timedelta(days=days)
        return cls.objects.filter(
            viewed_at__gte=since
        ).values('product').annotate(
            view_count=models.Count('id')
        ).order_by('-view_count')[:limit]


class ProductComparison(models.Model):
    """Track product comparisons for analytics"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='comparisons'
    )
    session_key = models.CharField(max_length=40, blank=True)
    products = models.ManyToManyField('products.Product', related_name='in_comparisons')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'product_comparisons'
        verbose_name = 'Product Comparison'
        verbose_name_plural = 'Product Comparisons'
        ordering = ['-created_at']
    
    def __str__(self):
        user_str = self.user.email if self.user else self.session_key
        return f"Comparison by {user_str}"

