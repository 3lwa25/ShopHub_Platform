"""
Global Notification System Models
"""
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse, NoReverseMatch


class Notification(models.Model):
    """
    Global notification model for all types of notifications
    """
    NOTIFICATION_TYPES = [
        ('order', 'Order'),
        ('reward', 'Reward'),
        ('product', 'Product'),
        ('payment', 'Payment'),
        ('shipment', 'Shipment'),
        ('system', 'System'),
        ('promotion', 'Promotion'),
        ('points_earned', 'Points Earned'),
        ('tier_upgrade', 'Tier Upgrade'),
        ('review', 'Review'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='system'
    )
    link = models.CharField(max_length=500, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"
    
    @classmethod
    def create_notification(cls, user, title, message, notification_type='system', link=None, metadata=None):
        """Helper method to create notifications"""
        if user is None:
            return None
        return cls.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link,
            metadata=metadata or {},
        )

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def get_resolved_link(self):
        if not self.link:
            return None

        link = self.link
        if link.startswith('http://') or link.startswith('https://'):
            return link
        if link.startswith('/'):
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            return f"{site_url}{link}"

        metadata = self.metadata or {}
        try:
            if ':' in link and metadata.get('resolver_args'):
                url = reverse(link, args=metadata['resolver_args'])
            elif ':' in link and metadata.get('resolver_kwargs'):
                url = reverse(link, kwargs=metadata['resolver_kwargs'])
            else:
                url = reverse(link)
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            return f"{site_url}{url}"
        except (NoReverseMatch, AttributeError):
            return link

