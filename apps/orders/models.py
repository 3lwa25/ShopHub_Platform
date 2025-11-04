"""
Shopping Cart and Order Management Models for Shop Hub
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.conf import settings
from apps.products.models import Product, ProductVariant
from apps.accounts.models import SellerProfile
import uuid


class Cart(models.Model):
    """
    Shopping cart for buyers.
    One cart per user.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
        primary_key=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'carts'
        verbose_name = _('Shopping Cart')
        verbose_name_plural = _('Shopping Carts')
    
    def __str__(self):
        return f"Cart for {self.user.email}"
    
    @property
    def total_items(self):
        """Total number of items (including quantities)"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def total_price(self):
        """Total cart price"""
        return sum(item.subtotal for item in self.items.all())
    
    def clear(self):
        """Remove all items from cart"""
        self.items.all().delete()


class CartItem(models.Model):
    """
    Individual items in a shopping cart.
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
        db_index=True
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items',
        db_index=True
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart_items'
    )
    
    # Quantity
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    
    # Timestamps
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_items'
        verbose_name = _('Cart Item')
        verbose_name_plural = _('Cart Items')
        unique_together = [['cart', 'product', 'variant']]
        ordering = ['-added_at']
        indexes = [
            models.Index(fields=['cart', 'product']),
        ]
    
    def __str__(self):
        variant_info = f" ({self.variant})" if self.variant else ""
        return f"{self.quantity}x {self.product.title}{variant_info}"
    
    @property
    def unit_price(self):
        """Get unit price (variant price if applicable)"""
        if self.variant:
            return self.variant.final_price
        return self.product.price
    
    @property
    def subtotal(self):
        """Calculate subtotal for this cart item"""
        return self.unit_price * self.quantity
    
    def save(self, *args, **kwargs):
        # Validate stock availability
        available_stock = self.variant.stock if self.variant else self.product.stock
        if self.quantity > available_stock:
            raise ValueError(f"Only {available_stock} items available in stock")
        super().save(*args, **kwargs)


class Order(models.Model):
    """
    Customer orders with status tracking.
    """
    STATUS_CHOICES = [
        ('CREATED', 'Created'),
        ('PENDING_PAYMENT', 'Pending Payment'),
        ('PAID', 'Paid'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('OUT_FOR_DELIVERY', 'Out for Delivery'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
        ('RETURN_REQUESTED', 'Return Requested'),
        ('RETURNED', 'Returned'),
    ]
    
    # Order identification
    order_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('Unique order number')
    )
    
    # Buyer relationship
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='orders',
        db_index=True
    )
    
    # Order financials
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Total order amount (EGP)')
    )
    currency = models.CharField(max_length=3, default='EGP')
    
    # Order status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='CREATED',
        db_index=True
    )
    
    # Shipping information (JSON field for flexibility)
    shipping_address = models.JSONField(
        help_text=_('Shipping address details (JSON)')
    )
    
    # Payment information
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        help_text=_('Payment method used')
    )
    payment_status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('refunded', 'Refunded'),
        ]
    )
    
    # Rewards integration
    reward_points_used = models.PositiveIntegerField(
        default=0,
        help_text=_('Reward points used for this order')
    )
    points_earned = models.PositiveIntegerField(
        default=0,
        help_text=_('Reward points earned from this order')
    )
    
    # Order notes
    customer_notes = models.TextField(
        blank=True,
        help_text=_('Special instructions from customer')
    )
    admin_notes = models.TextField(
        blank=True,
        help_text=_('Internal notes (not visible to customer)')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'orders'
        verbose_name = _('Order')
        verbose_name_plural = _('Orders')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer', 'status']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['order_number']),
        ]
    
    def __str__(self):
        return f"Order {self.order_number} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        # Auto-generate order number if not set
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_order_number():
        """Generate unique order number"""
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = str(uuid.uuid4().hex[:6]).upper()
        return f"ORD-{timestamp}-{random_part}"
    
    @property
    def item_count(self):
        """Total number of items in order"""
        return sum(item.quantity for item in self.items.all())
    
    def calculate_points_earned(self):
        """Calculate reward points based on total amount"""
        from django.conf import settings
        points_per_dollar = getattr(settings, 'POINTS_PER_DOLLAR', 10)
        # Convert to USD for points calculation (assuming 1 USD = 30 EGP)
        usd_amount = self.total_amount / 30
        return int(usd_amount * points_per_dollar)


class OrderItem(models.Model):
    """
    Individual items within an order.
    Preserves product information at time of purchase.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        db_index=True
    )
    
    # Product references (may be null if product deleted later)
    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_items'
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items'
    )
    
    # Seller reference
    seller = models.ForeignKey(
        SellerProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name='order_items',
        db_index=True
    )
    
    # Preserved product information (snapshot at purchase time)
    product_name = models.CharField(
        max_length=500,
        help_text=_('Product name at time of purchase')
    )
    product_sku = models.CharField(max_length=100, blank=True)
    
    # Pricing at purchase time
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Unit price at time of purchase (EGP)')
    )
    
    # Quantity
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    
    # Item status (for multi-seller orders where items ship separately)
    status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('shipped', 'Shipped'),
            ('delivered', 'Delivered'),
            ('cancelled', 'Cancelled'),
        ]
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'order_items'
        verbose_name = _('Order Item')
        verbose_name_plural = _('Order Items')
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['seller', 'status']),
        ]
    
    def __str__(self):
        return f"{self.quantity}x {self.product_name} (Order: {self.order.order_number})"
    
    @property
    def subtotal(self):
        """Calculate subtotal for this order item"""
        return self.unit_price * self.quantity


class ShipmentTracking(models.Model):
    """
    Shipment tracking information for orders.
    Supports tracking history with status updates.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='shipments',
        db_index=True
    )
    
    # Courier information
    courier_name = models.CharField(
        max_length=100,
        help_text=_('Shipping courier/company name')
    )
    tracking_number = models.CharField(
        max_length=100,
        db_index=True,
        help_text=_('Tracking number from courier')
    )
    
    # Current status
    current_status = models.CharField(
        max_length=50,
        default='pending',
        help_text=_('Current shipment status')
    )
    
    # Tracking history (JSON array of status updates)
    # Format: [{"status": "...", "timestamp": "...", "location": "..."}]
    history = models.JSONField(
        default=list,
        blank=True,
        help_text=_('Tracking history with timestamps and locations')
    )
    
    # Estimated delivery
    estimated_delivery = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Estimated delivery date/time')
    )
    
    # Actual delivery
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Actual delivery date/time')
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text=_('Additional shipping notes')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shipment_tracking'
        verbose_name = _('Shipment Tracking')
        verbose_name_plural = _('Shipment Tracking')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['tracking_number']),
            models.Index(fields=['current_status']),
        ]
    
    def __str__(self):
        return f"Shipment for {self.order.order_number} - {self.tracking_number}"
    
    def add_status_update(self, status, location=None, notes=None):
        """
        Add a new status update to tracking history.
        
        Args:
            status (str): Status update
            location (str): Location of package
            notes (str): Additional notes
        """
        import datetime
        
        update = {
            'status': status,
            'timestamp': datetime.datetime.now().isoformat(),
            'location': location or '',
        }
        
        if notes:
            update['notes'] = notes
        
        # Ensure history is a list
        if not isinstance(self.history, list):
            self.history = []
        
        self.history.append(update)
        self.current_status = status
        
        # Update delivered_at if status is delivered
        if status.lower() in ['delivered', 'completed']:
            self.delivered_at = datetime.datetime.now()
        
        self.save(update_fields=['history', 'current_status', 'delivered_at', 'updated_at'])

