"""
Order Management Models for Shop Hub
Note: Shopping Cart models are in apps.cart
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.conf import settings
from apps.products.models import Product, ProductVariant
from apps.accounts.models import SellerProfile
import uuid


# Cart models are now in apps.cart
# from apps.cart.models import Cart, CartItem


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
    subtotal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        help_text=_('Subtotal before discounts (EGP)')
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        help_text=_('Total discount applied (EGP)')
    )
    shipping_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        help_text=_('Shipping fee (EGP)')
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        default=0,
        help_text=_('Tax amount (EGP)')
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Total order amount after discounts, shipping, and tax (EGP)')
    )
    currency = models.CharField(max_length=3, default='EGP')
    
    # Coupon information
    coupon_code = models.CharField(
        max_length=50,
        blank=True,
        help_text=_('Applied coupon code')
    )
    
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
    
    STATUS_CHOICES = [
        ('ordered', 'Ordered'),
        ('confirmed', 'Confirmed'),
        ('on_pack', 'On Pack'),
        ('dispatched', 'Dispatched'),
        ('out_to_delivery', 'Out to Delivery'),
        ('delivered', 'Delivered'),
    ]
    
    # Current status
    current_status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='ordered',
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
    
    def add_status_update(self, status, location=None, notes=None, updated_by='seller'):
        """
        Add a new status update to tracking history.
        
        Args:
            status (str): Status update
            location (str): Location of package
            notes (str): Additional notes
        """
        from django.utils import timezone
        
        update = {
            'status': status,
            'timestamp': timezone.now().isoformat(),
            'location': location or '',
            'updated_by': updated_by or 'system',
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
            self.delivered_at = timezone.now()
        
        self.save(update_fields=['history', 'current_status', 'delivered_at', 'updated_at'])


class PaymentTransaction(models.Model):
    """
    Payment transaction records for orders.
    Stores detailed payment information (placeholder for real integration).
    """
    PAYMENT_METHOD_CHOICES = [
        ('cod', 'Cash on Delivery'),
        ('credit_card', 'Credit Card'),
        ('debit_card', 'Debit Card'),
        ('paypal', 'PayPal'),
        ('stripe', 'Stripe'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_wallet', 'Mobile Wallet'),
    ]
    
    TRANSACTION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    ]
    
    # Transaction identification
    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text=_('Unique transaction ID')
    )
    
    # Order relationship
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='payment_transactions',
        db_index=True
    )
    
    # Payment details
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        help_text=_('Payment method used')
    )
    
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Transaction amount')
    )
    
    currency = models.CharField(max_length=3, default='EGP')
    
    status = models.CharField(
        max_length=20,
        choices=TRANSACTION_STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    
    # Payment gateway info (placeholder)
    gateway_name = models.CharField(
        max_length=50,
        blank=True,
        help_text=_('Payment gateway name')
    )
    gateway_transaction_id = models.CharField(
        max_length=200,
        blank=True,
        help_text=_('Transaction ID from payment gateway')
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Response from payment gateway (JSON)')
    )
    
    # Card details (masked, for display only)
    card_last4 = models.CharField(
        max_length=4,
        blank=True,
        help_text=_('Last 4 digits of card')
    )
    card_brand = models.CharField(
        max_length=20,
        blank=True,
        help_text=_('Card brand (Visa, Mastercard, etc.)')
    )
    
    # Transaction metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_('IP address of transaction')
    )
    user_agent = models.TextField(
        blank=True,
        help_text=_('User agent string')
    )
    
    # Payment summary fields
    platform_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_('Platform fee (EGP)')
    )
    processing_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_('Processing fee (EGP)')
    )
    net_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_('Net amount after fees (EGP)')
    )
    payment_summary = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Payment summary details (JSON)')
    )
    
    # Refund information
    refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_('Amount refunded')
    )
    refund_reason = models.TextField(
        blank=True,
        help_text=_('Reason for refund')
    )
    refunded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Date/time of refund')
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text=_('Internal notes about transaction')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Date/time transaction was completed')
    )
    
    class Meta:
        db_table = 'payment_transactions'
        verbose_name = _('Payment Transaction')
        verbose_name_plural = _('Payment Transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['status', '-created_at']),
        ]
    
    def __str__(self):
        return f"Transaction {self.transaction_id} - {self.get_payment_method_display()} - {self.get_status_display()}"
    
    def save(self, *args, **kwargs):
        # Auto-generate transaction ID if not set
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_transaction_id():
        """Generate unique transaction ID"""
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = str(uuid.uuid4().hex[:8]).upper()
        return f"TXN-{timestamp}-{random_part}"
    
    @property
    def is_refundable(self):
        """Check if transaction can be refunded"""
        return self.status == 'completed' and self.refund_amount < self.amount
    
    @property
    def remaining_refundable_amount(self):
        """Calculate remaining amount that can be refunded"""
        return self.amount - self.refund_amount


class Invoice(models.Model):
    """
    Invoice records for orders.
    """
    # Invoice identification
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text=_('Unique invoice number')
    )
    
    # Order relationship
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='invoice',
        db_index=True
    )
    
    # Invoice details
    issue_date = models.DateField(
        auto_now_add=True,
        help_text=_('Date invoice was issued')
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text=_('Payment due date')
    )
    
    # Amounts
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Subtotal before tax and shipping')
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_('Tax amount')
    )
    shipping_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_('Shipping cost')
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text=_('Discount amount')
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Total invoice amount')
    )
    
    # Invoice status
    is_paid = models.BooleanField(
        default=False,
        help_text=_('Whether invoice has been paid')
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_('Date/time invoice was paid')
    )
    
    # PDF generation
    pdf_file = models.FileField(
        upload_to='invoices/%Y/%m/',
        null=True,
        blank=True,
        help_text=_('Generated PDF invoice')
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        help_text=_('Additional notes on invoice')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'invoices'
        verbose_name = _('Invoice')
        verbose_name_plural = _('Invoices')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number} for Order {self.order.order_number}"
    
    def save(self, *args, **kwargs):
        # Auto-generate invoice number if not set
        if not self.invoice_number:
            self.invoice_number = self.generate_invoice_number()
        super().save(*args, **kwargs)
    
    @staticmethod
    def generate_invoice_number():
        """Generate unique invoice number"""
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = str(uuid.uuid4().hex[:4]).upper()
        return f"INV-{timestamp}-{random_part}"

