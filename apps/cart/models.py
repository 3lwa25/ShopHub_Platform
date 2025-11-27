"""
Shopping Cart Models for Shop Hub
Handles cart and cart items for authenticated and anonymous users
"""
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from apps.products.models import Product


class Cart(models.Model):
    """
    Shopping cart model.
    Each user can have one active cart.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Cart owner (null for anonymous carts)')
    )
    
    # For anonymous carts, use session key
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        db_index=True,
        help_text=_('Session key for anonymous users')
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shopping_carts'
        verbose_name = _('Cart')
        verbose_name_plural = _('Carts')
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['session_key']),
            models.Index(fields=['updated_at']),
        ]
    
    def __str__(self):
        if self.user:
            return f"Cart of {self.user.full_name or self.user.email}"
        return f"Anonymous Cart ({self.session_key[:10]}...)"
    
    @property
    def total_items(self):
        """Get total number of items in cart"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def total_price(self):
        """Calculate total price of all items in cart"""
        return sum(item.subtotal for item in self.items.all())
    
    @property
    def total_savings(self):
        """Calculate total savings from discounts"""
        savings = 0
        for item in self.items.all():
            if item.product.is_on_sale:
                original_price = item.product.compare_at_price * item.quantity
                current_price = item.product.price * item.quantity
                savings += (original_price - current_price)
        return savings
    
    def clear(self):
        """Remove all items from cart"""
        self.items.all().delete()
    
    def merge_with_user_cart(self, user):
        """
        Merge anonymous cart with user's cart after login
        """
        if not user or not user.is_authenticated:
            return
        
        try:
            user_cart = Cart.objects.get(user=user)
            # Merge items
            for item in self.items.all():
                existing_item = user_cart.items.filter(product=item.product).first()
                if existing_item:
                    # Update quantity
                    existing_item.quantity += item.quantity
                    existing_item.save()
                else:
                    # Move item to user cart
                    item.cart = user_cart
                    item.save()
            # Delete anonymous cart
            self.delete()
        except Cart.DoesNotExist:
            # No existing user cart, just assign user
            self.user = user
            self.session_key = None
            self.save()


class CartItem(models.Model):
    """
    Individual items in the shopping cart
    """
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items',
        db_index=True,
        help_text=_('Cart this item belongs to')
    )
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items',
        db_index=True,
        help_text=_('Product in cart')
    )
    
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text=_('Quantity of this product')
    )
    
    # Price at the time of adding to cart (for historical tracking)
    price_at_addition = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text=_('Price when added to cart')
    )
    
    # Timestamps
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'shopping_cart_items'
        verbose_name = _('Cart Item')
        verbose_name_plural = _('Cart Items')
        ordering = ['-added_at']
        unique_together = [['cart', 'product']]
        indexes = [
            models.Index(fields=['cart', 'product']),
            models.Index(fields=['added_at']),
        ]
    
    def __str__(self):
        return f"{self.quantity}x {self.product.title} in cart"
    
    @property
    def subtotal(self):
        """Calculate subtotal for this item (current price x quantity)"""
        return self.product.price * self.quantity
    
    @property
    def original_subtotal(self):
        """Calculate original subtotal if product is on sale"""
        if self.product.is_on_sale:
            return self.product.compare_at_price * self.quantity
        return self.subtotal
    
    @property
    def savings(self):
        """Calculate savings for this item"""
        if self.product.is_on_sale:
            return self.original_subtotal - self.subtotal
        return 0
    
    @property
    def is_in_stock(self):
        """Check if product has enough stock"""
        return self.product.stock >= self.quantity
    
    @property
    def max_quantity_available(self):
        """Get maximum quantity available for this product"""
        return self.product.stock
    
    def save(self, *args, **kwargs):
        # Set price at addition if not already set
        if not self.price_at_addition:
            self.price_at_addition = self.product.price
        
        # Ensure quantity doesn't exceed stock
        if self.quantity > self.product.stock:
            self.quantity = self.product.stock
        
        super().save(*args, **kwargs)
        
        # Update cart's updated_at timestamp
        self.cart.save()
    
    def increase_quantity(self, amount=1):
        """Increase quantity by amount (default 1)"""
        new_quantity = self.quantity + amount
        if new_quantity <= self.product.stock:
            self.quantity = new_quantity
            self.save()
            return True
        return False
    
    def decrease_quantity(self, amount=1):
        """Decrease quantity by amount (default 1)"""
        new_quantity = self.quantity - amount
        if new_quantity >= 1:
            self.quantity = new_quantity
            self.save()
            return True
        return False
