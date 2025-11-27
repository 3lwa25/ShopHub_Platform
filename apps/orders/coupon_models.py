"""
Coupon and Discount Models
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal


class Coupon(models.Model):
    """Coupon codes for discounts"""
    
    DISCOUNT_TYPE_CHOICES = [
        ('percentage', 'Percentage Discount'),
        ('fixed', 'Fixed Amount Discount'),
        ('free_shipping', 'Free Shipping'),
    ]
    
    code = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text='Unique coupon code'
    )
    description = models.TextField(
        blank=True,
        help_text='Internal description of the coupon'
    )
    
    # Discount details
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default='percentage'
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Percentage (0-100) or fixed amount'
    )
    
    # Conditions
    min_order_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Minimum order value to apply coupon'
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Maximum discount amount (for percentage coupons)'
    )
    
    # Categories and products
    applicable_categories = models.ManyToManyField(
        'products.Category',
        blank=True,
        related_name='coupons',
        help_text='Apply only to these categories (empty = all)'
    )
    applicable_products = models.ManyToManyField(
        'products.Product',
        blank=True,
        related_name='coupons',
        help_text='Apply only to these products (empty = all)'
    )
    
    # Usage limits
    max_uses = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text='Total usage limit (null = unlimited)'
    )
    max_uses_per_user = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Usage limit per user'
    )
    current_uses = models.IntegerField(
        default=0,
        help_text='Current number of uses'
    )
    
    # Validity period
    valid_from = models.DateTimeField(
        default=timezone.now,
        help_text='Coupon valid from this date'
    )
    valid_to = models.DateTimeField(
        help_text='Coupon valid until this date'
    )
    
    # User restrictions
    first_order_only = models.BooleanField(
        default=False,
        help_text='Only for users with no previous orders'
    )
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='exclusive_coupons',
        help_text='Restrict to specific users (empty = all users)'
    )
    
    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text='Is this coupon active?'
    )
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_coupons'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'coupons'
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['code', 'is_active']),
            models.Index(fields=['valid_from', 'valid_to']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.get_discount_display()}"
    
    def get_discount_display(self):
        """Human-readable discount"""
        if self.discount_type == 'percentage':
            return f"{self.discount_value}% off"
        elif self.discount_type == 'fixed':
            return f"EGP {self.discount_value} off"
        else:
            return "Free shipping"
    
    def is_valid(self, user=None):
        """Check if coupon is currently valid"""
        now = timezone.now()
        
        # Check active status
        if not self.is_active:
            return False, "This coupon is not active."
        
        # Check date validity
        if now < self.valid_from:
            return False, f"This coupon is not yet valid. Valid from {self.valid_from.strftime('%Y-%m-%d')}."
        if now > self.valid_to:
            return False, "This coupon has expired."
        
        # Check usage limits
        if self.max_uses and self.current_uses >= self.max_uses:
            return False, "This coupon has reached its usage limit."
        
        # Check user-specific restrictions
        if user:
            # Check user limit
            user_uses = CouponUsage.objects.filter(coupon=self, user=user).count()
            if user_uses >= self.max_uses_per_user:
                return False, "You have already used this coupon the maximum number of times."
            
            # Check first order only
            if self.first_order_only:
                from apps.orders.models import Order
                if Order.objects.filter(buyer=user).exists():
                    return False, "This coupon is only for first-time customers."
            
            # Check allowed users
            if self.allowed_users.exists() and user not in self.allowed_users.all():
                return False, "This coupon is not available for your account."
        
        return True, "Coupon is valid."
    
    def calculate_discount(self, order_total, cart_items=None):
        """Calculate discount amount for given order total"""
        if self.discount_type == 'percentage':
            discount = (order_total * self.discount_value) / Decimal('100.00')
            if self.max_discount_amount:
                discount = min(discount, self.max_discount_amount)
            return discount
        elif self.discount_type == 'fixed':
            return min(self.discount_value, order_total)
        else:  # free_shipping
            return Decimal('0.00')  # Shipping discount handled separately
    
    def can_apply_to_cart(self, cart_items):
        """Check if coupon can be applied to given cart items"""
        if not cart_items:
            return False
        
        # If no specific restrictions, apply to all
        if not self.applicable_categories.exists() and not self.applicable_products.exists():
            return True
        
        # Check if any item matches restrictions
        for item in cart_items:
            # Check product restriction
            if self.applicable_products.exists():
                if item.product in self.applicable_products.all():
                    return True
            
            # Check category restriction
            if self.applicable_categories.exists():
                if item.product.category in self.applicable_categories.all():
                    return True
        
        return False
    
    def increment_usage(self):
        """Increment usage counter"""
        self.current_uses += 1
        self.save(update_fields=['current_uses'])


class CouponUsage(models.Model):
    """Track coupon usage"""
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name='usages'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coupon_usages'
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.CASCADE,
        related_name='coupon_usages'
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Actual discount applied'
    )
    used_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'coupon_usages'
        verbose_name = 'Coupon Usage'
        verbose_name_plural = 'Coupon Usages'
        ordering = ['-used_at']
        indexes = [
            models.Index(fields=['coupon', 'user']),
            models.Index(fields=['order']),
        ]
    
    def __str__(self):
        return f"{self.user.email} used {self.coupon.code} on {self.order.order_number}"

