"""
Wishlist Models for Shop Hub
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from apps.products.models import Product


class Wishlist(models.Model):
    """
    User wishlist.
    One wishlist per user.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist',
        primary_key=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wishlists'
        verbose_name = _('Wishlist')
        verbose_name_plural = _('Wishlists')
    
    def __str__(self):
        return f"Wishlist for {self.user.email}"
    
    @property
    def item_count(self):
        """Total number of items in wishlist"""
        return self.items.count()
    
    def add_product(self, product):
        """
        Add product to wishlist.
        
        Args:
            product (Product): Product to add
        
        Returns:
            WishlistItem: Created wishlist item or existing one
        """
        item, created = WishlistItem.objects.get_or_create(
            wishlist=self,
            product=product
        )
        return item
    
    def remove_product(self, product):
        """
        Remove product from wishlist.
        
        Args:
            product (Product): Product to remove
        """
        WishlistItem.objects.filter(
            wishlist=self,
            product=product
        ).delete()
    
    def has_product(self, product):
        """
        Check if product is in wishlist.
        
        Args:
            product (Product): Product to check
        
        Returns:
            bool: True if product is in wishlist
        """
        return self.items.filter(product=product).exists()


class WishlistItem(models.Model):
    """
    Individual items in a wishlist.
    """
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name='items',
        db_index=True
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='wishlist_items',
        db_index=True
    )
    
    # Note (optional - user can add notes about why they want this product)
    notes = models.TextField(
        blank=True,
        help_text=_('Personal notes about this product')
    )
    
    # Priority (optional - for organizing wishlist)
    priority = models.PositiveSmallIntegerField(
        default=0,
        help_text=_('Priority (higher number = higher priority)')
    )
    
    # Timestamps
    added_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wishlist_items'
        verbose_name = _('Wishlist Item')
        verbose_name_plural = _('Wishlist Items')
        unique_together = [['wishlist', 'product']]
        ordering = ['-priority', '-added_at']
        indexes = [
            models.Index(fields=['wishlist', 'product']),
            models.Index(fields=['-priority', '-added_at']),
        ]
    
    def __str__(self):
        return f"{self.product.title} in {self.wishlist.user.email}'s wishlist"
    
    @property
    def is_in_stock(self):
        """Check if product is in stock"""
        return self.product.is_in_stock
    
    @property
    def is_on_sale(self):
        """Check if product is on sale"""
        return self.product.is_on_sale

