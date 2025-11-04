"""
Virtual Try-On Models for Shop Hub
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from apps.products.models import Product
import uuid


class VTOAsset(models.Model):
    """
    Virtual Try-On assets for products.
    Stores overlay images and positioning data for face-api.js client-side rendering.
    """
    ASSET_TYPES = [
        ('glasses', 'Glasses/Eyewear'),
        ('hat', 'Hat/Headwear'),
        ('mask', 'Face Mask'),
        ('jewelry', 'Jewelry'),
        ('accessory', 'Accessory'),
    ]
    
    # Product relationship
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='vto_assets',
        db_index=True,
        help_text=_('Product this VTO asset belongs to')
    )
    
    # Asset type
    asset_type = models.CharField(
        max_length=20,
        choices=ASSET_TYPES,
        db_index=True,
        help_text=_('Type of VTO asset')
    )
    
    # Overlay image (transparent PNG)
    overlay_image = models.ImageField(
        upload_to='vto/overlays/%Y/%m/',
        help_text=_('Transparent PNG overlay image')
    )
    
    # Positioning data for client-side rendering
    anchor_points = models.JSONField(
        default=dict,
        help_text=_('Anchor points for positioning (JSON)')
    )
    
    # Scaling factor
    scale_factor = models.FloatField(
        default=1.0,
        help_text=_('Scale factor for overlay size')
    )
    
    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Additional VTO configuration (JSON)')
    )
    
    # Active status
    is_active = models.BooleanField(
        default=True,
        help_text=_('Is this VTO asset active?')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'vto_assets'
        verbose_name = _('VTO Asset')
        verbose_name_plural = _('VTO Assets')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['asset_type']),
        ]
    
    def __str__(self):
        return f"{self.get_asset_type_display()} for {self.product.title}"


class TryonSession(models.Model):
    """
    Virtual Try-On session tracking.
    Tracks user sessions for analytics.
    """
    # User (nullable for guests)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tryon_sessions',
        db_index=True
    )
    
    # Session identifier
    session_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        default=uuid.uuid4,
        help_text=_('Unique session identifier')
    )
    
    # Session metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Session metadata (device, browser, etc.)')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'tryon_sessions'
        verbose_name = _('Try-On Session')
        verbose_name_plural = _('Try-On Sessions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        user_str = self.user.email if self.user else 'Guest'
        return f"Session {self.session_id[:8]} - {user_str}"
    
    @property
    def is_active(self):
        """Check if session is still active"""
        return self.ended_at is None
    
    def end_session(self):
        """Mark session as ended"""
        from django.utils import timezone
        if not self.ended_at:
            self.ended_at = timezone.now()
            self.save(update_fields=['ended_at'])


class TryonImage(models.Model):
    """
    Stores user-uploaded photos and VTO results.
    For privacy, images should be auto-deleted after a period.
    """
    # Session relationship
    session = models.ForeignKey(
        TryonSession,
        on_delete=models.CASCADE,
        related_name='images',
        db_index=True
    )
    
    # Product tried on
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tryon_images'
    )
    
    # User's uploaded photo
    user_photo = models.ImageField(
        upload_to='vto/user_photos/%Y/%m/%d/',
        help_text=_('User uploaded photo')
    )
    
    # Result image (with overlay applied - optional, client-side rendering)
    result_image = models.ImageField(
        upload_to='vto/results/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text=_('Result image with product overlay')
    )
    
    # Processing status
    status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        db_index=True
    )
    
    # Face detection results (from face-api.js)
    face_data = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Face detection landmarks and data')
    )
    
    # Privacy: Auto-delete flag
    auto_delete_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('When to auto-delete for privacy (GDPR compliance)')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tryon_images'
        verbose_name = _('Try-On Image')
        verbose_name_plural = _('Try-On Images')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', '-created_at']),
            models.Index(fields=['product']),
            models.Index(fields=['status']),
            models.Index(fields=['auto_delete_at']),
        ]
    
    def __str__(self):
        return f"Try-on {self.id} - {self.product.title if self.product else 'No product'}"
    
    def save(self, *args, **kwargs):
        # Set auto-delete time (30 days from creation)
        if not self.auto_delete_at:
            from django.utils import timezone
            from datetime import timedelta
            self.auto_delete_at = timezone.now() + timedelta(days=30)
        super().save(*args, **kwargs)
    
    @property
    def is_completed(self):
        """Check if VTO processing is completed"""
        return self.status == 'completed'
    
    @classmethod
    def cleanup_old_images(cls):
        """
        Delete old images past their auto_delete_at date.
        Should be called by a scheduled task (Celery).
        """
        from django.utils import timezone
        
        old_images = cls.objects.filter(
            auto_delete_at__lte=timezone.now()
        )
        
        count = old_images.count()
        
        # Delete image files
        for image in old_images:
            if image.user_photo:
                image.user_photo.delete()
            if image.result_image:
                image.result_image.delete()
        
        # Delete records
        old_images.delete()
        
        return count

