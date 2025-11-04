"""
Product Reviews Models for Shop Hub
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
from apps.products.models import Product
from apps.orders.models import Order


class Review(models.Model):
    """
    Product reviews by customers.
    Only buyers who purchased the product can review.
    """
    # Product and user
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='reviews',
        db_index=True
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews',
        db_index=True
    )
    
    # Order reference (for verification)
    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviews',
        help_text=_('Order that included this product')
    )
    
    # Rating (1-5 stars)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text=_('Rating from 1 to 5 stars')
    )
    
    # Review content
    title = models.CharField(
        max_length=255,
        help_text=_('Review title/headline')
    )
    body = models.TextField(
        help_text=_('Review content/description')
    )
    
    # Verification
    verified_purchase = models.BooleanField(
        default=False,
        db_index=True,
        help_text=_('Review from verified purchase')
    )
    
    # Community engagement
    helpful_count = models.PositiveIntegerField(
        default=0,
        help_text=_('Number of users who found this review helpful')
    )
    
    # Moderation
    status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'Pending Review'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ],
        db_index=True
    )
    
    # Seller response
    seller_response = models.TextField(
        blank=True,
        help_text=_('Response from seller')
    )
    seller_responded_at = models.DateTimeField(
        null=True,
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'reviews'
        verbose_name = _('Product Review')
        verbose_name_plural = _('Product Reviews')
        ordering = ['-created_at']
        unique_together = [['buyer', 'product']]  # One review per user per product
        indexes = [
            models.Index(fields=['product', 'status']),
            models.Index(fields=['buyer']),
            models.Index(fields=['rating']),
            models.Index(fields=['verified_purchase']),
            models.Index(fields=['-helpful_count']),
        ]
    
    def __str__(self):
        return f"{self.rating}★ - {self.title} by {self.buyer.email}"
    
    def save(self, *args, **kwargs):
        # Auto-verify purchase if order is provided
        if self.order and not self.verified_purchase:
            # Check if order contains this product
            if self.order.items.filter(product=self.product).exists():
                self.verified_purchase = True
        
        super().save(*args, **kwargs)
        
        # Update product rating after save
        self.product.update_rating()
    
    def delete(self, *args, **kwargs):
        product = self.product
        super().delete(*args, **kwargs)
        # Update product rating after delete
        product.update_rating()
    
    @property
    def star_display(self):
        """Return star rating as string (e.g., '★★★★☆')"""
        return '★' * self.rating + '☆' * (5 - self.rating)


class ReviewImage(models.Model):
    """
    Images attached to product reviews.
    Customers can upload photos with their reviews.
    """
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='images',
        db_index=True
    )
    
    # Image file
    image = models.ImageField(
        upload_to='reviews/%Y/%m/',
        help_text=_('Review image uploaded by customer')
    )
    
    # Image metadata
    caption = models.CharField(
        max_length=255,
        blank=True,
        help_text=_('Optional image caption')
    )
    
    # Display order
    display_order = models.PositiveIntegerField(
        default=0,
        help_text=_('Display order (lower numbers first)')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'review_images'
        verbose_name = _('Review Image')
        verbose_name_plural = _('Review Images')
        ordering = ['display_order', 'created_at']
        indexes = [
            models.Index(fields=['review', 'display_order']),
        ]
    
    def __str__(self):
        return f"Image for review #{self.review.id}"


class ReviewHelpful(models.Model):
    """
    Track which users marked a review as helpful.
    Prevents duplicate votes.
    """
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='helpful_votes'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='helpful_reviews'
    )
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'review_helpful'
        verbose_name = _('Helpful Vote')
        verbose_name_plural = _('Helpful Votes')
        unique_together = [['review', 'user']]
        indexes = [
            models.Index(fields=['review']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user.email} found review #{self.review.id} helpful"

