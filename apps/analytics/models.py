"""
Analytics and User Interaction Models for Shop Hub
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from apps.products.models import Product


class Event(models.Model):
    """
    User interaction events for analytics and recommendations.
    Tracks views, cart additions, purchases, and try-on sessions.
    """
    EVENT_TYPES = [
        ('view', 'Product View'),
        ('add_to_cart', 'Add to Cart'),
        ('purchase', 'Purchase'),
        ('tryon', 'Virtual Try-On'),
        ('wishlist', 'Add to Wishlist'),
        ('review', 'Product Review'),
        ('search', 'Search Query'),
    ]
    
    # User (nullable for guest users)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='events',
        db_index=True,
        help_text=_('User who performed the action (null for guests)')
    )
    
    # Product (nullable for non-product events like search)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='events',
        db_index=True,
        help_text=_('Product involved in the event')
    )
    
    # Event type
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPES,
        db_index=True,
        help_text=_('Type of event/interaction')
    )
    
    # Session tracking
    session_id = models.CharField(
        max_length=100,
        db_index=True,
        help_text=_('Session identifier for tracking user journey')
    )
    
    # Additional event metadata (JSON for flexibility)
    # Can store: search query, device type, referrer, cart quantity, etc.
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Additional event data (JSON)')
    )
    
    # User agent and IP (for analytics)
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        help_text=_('Browser user agent')
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_('User IP address (anonymized for GDPR compliance)')
    )
    
    # Timestamp
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'events'
        verbose_name = _('User Event')
        verbose_name_plural = _('User Events')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['product', '-timestamp']),
            models.Index(fields=['event_type', '-timestamp']),
            models.Index(fields=['session_id', '-timestamp']),
        ]
    
    def __str__(self):
        user_str = self.user.email if self.user else 'Guest'
        product_str = self.product.title if self.product else 'N/A'
        return f"{user_str} - {self.get_event_type_display()} - {product_str}"
    
    @classmethod
    def log_event(cls, event_type, session_id, user=None, product=None, metadata=None, 
                  user_agent='', ip_address=None):
        """
        Helper method to log an event.
        
        Args:
            event_type (str): Type of event
            session_id (str): Session identifier
            user (User): User object (optional)
            product (Product): Product object (optional)
            metadata (dict): Additional event data
            user_agent (str): Browser user agent
            ip_address (str): User IP address
        
        Returns:
            Event: Created event object
        """
        return cls.objects.create(
            user=user,
            product=product,
            event_type=event_type,
            session_id=session_id,
            metadata=metadata or {},
            user_agent=user_agent,
            ip_address=ip_address
        )
    
    @classmethod
    def get_user_interactions(cls, user, limit=100):
        """
        Get recent interactions for a user.
        Used for personalized recommendations.
        
        Args:
            user (User): User object
            limit (int): Maximum number of interactions to return
        
        Returns:
            QuerySet: Recent user events
        """
        return cls.objects.filter(user=user).order_by('-timestamp')[:limit]
    
    @classmethod
    def get_product_views(cls, product, days=30):
        """
        Get view count for a product in the last N days.
        
        Args:
            product (Product): Product object
            days (int): Number of days to look back
        
        Returns:
            int: View count
        """
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        return cls.objects.filter(
            product=product,
            event_type='view',
            timestamp__gte=cutoff_date
        ).count()
    
    @classmethod
    def get_trending_products(cls, days=7, limit=10):
        """
        Get trending products based on recent interactions.
        
        Args:
            days (int): Number of days to analyze
            limit (int): Number of products to return
        
        Returns:
            QuerySet: Top trending products
        """
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        return Product.objects.filter(
            events__timestamp__gte=cutoff_date,
            events__event_type__in=['view', 'add_to_cart', 'purchase']
        ).annotate(
            interaction_count=Count('events')
        ).order_by('-interaction_count')[:limit]

