"""
Admin configuration for Wishlist
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Wishlist, WishlistItem


class WishlistItemInline(admin.TabularInline):
    """Inline admin for wishlist items"""
    model = WishlistItem
    extra = 0
    fields = ('product', 'notes', 'priority', 'added_at')
    readonly_fields = ('added_at',)


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    """Admin for Wishlists"""
    list_display = ['user_link', 'item_count', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__email', 'user__full_name']
    readonly_fields = ['created_at', 'updated_at', 'item_count']
    inlines = [WishlistItemInline]
    
    def user_link(self, obj):
        """Link to user"""
        return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
    user_link.short_description = 'User'
    
    def item_count(self, obj):
        """Display item count"""
        return obj.items.count()
    item_count.short_description = 'Items'


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    """Admin for Wishlist Items"""
    list_display = ['id', 'wishlist_link', 'product_link', 'priority', 'is_in_stock', 'added_at']
    list_filter = ['priority', 'added_at', 'product__stock']
    search_fields = ['product__title', 'wishlist__user__email', 'notes']
    readonly_fields = ['added_at', 'updated_at', 'is_in_stock', 'is_on_sale']
    
    def wishlist_link(self, obj):
        """Link to wishlist"""
        return format_html('<a href="/admin/wishlist/wishlist/{}/change/">{}</a>', obj.wishlist.user.id, obj.wishlist.user.email)
    wishlist_link.short_description = 'Wishlist'
    
    def product_link(self, obj):
        """Link to product"""
        return format_html('<a href="/admin/products/product/{}/change/">{}</a>', obj.product.id, obj.product.title)
    product_link.short_description = 'Product'
    
    def is_in_stock(self, obj):
        """Check stock status"""
        return obj.product.is_in_stock
    is_in_stock.boolean = True
    is_in_stock.short_description = 'In Stock'
    
    def is_on_sale(self, obj):
        """Check sale status"""
        return obj.product.is_on_sale
    is_on_sale.boolean = True
    is_on_sale.short_description = 'On Sale'
