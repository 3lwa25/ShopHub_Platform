"""
Admin configuration for Shopping Cart
"""
from django.contrib import admin
from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    """Inline display of cart items"""
    model = CartItem
    extra = 0
    readonly_fields = ['added_at', 'updated_at', 'price_at_addition', 'subtotal']
    fields = ['product', 'quantity', 'price_at_addition', 'subtotal', 'added_at']
    
    def subtotal(self, obj):
        return f"EGP {obj.subtotal:.2f}"
    subtotal.short_description = 'Subtotal'


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """Admin configuration for Cart model"""
    list_display = ['id', 'user_display', 'total_items', 'total_price_display', 'created_at', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__email', 'user__full_name', 'session_key']
    readonly_fields = ['created_at', 'updated_at', 'total_items', 'total_price_display', 'total_savings_display']
    inlines = [CartItemInline]
    ordering = ['-updated_at']
    
    fieldsets = (
        ('Cart Information', {
            'fields': ('user', 'session_key')
        }),
        ('Cart Summary', {
            'fields': ('total_items', 'total_price_display', 'total_savings_display')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_display(self, obj):
        if obj.user:
            return f"{obj.user.full_name or obj.user.email}"
        return f"Anonymous ({obj.session_key[:10]}...)"
    user_display.short_description = 'User'
    
    def total_price_display(self, obj):
        return f"EGP {obj.total_price:.2f}"
    total_price_display.short_description = 'Total Price'
    
    def total_savings_display(self, obj):
        return f"EGP {obj.total_savings:.2f}"
    total_savings_display.short_description = 'Total Savings'
    
    def has_add_permission(self, request):
        # Disable manual cart creation
        return False


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """Admin configuration for CartItem model"""
    list_display = ['id', 'cart_display', 'product', 'quantity', 'price_at_addition', 'subtotal_display', 'is_in_stock', 'added_at']
    list_filter = ['added_at', 'updated_at']
    search_fields = ['product__title', 'cart__user__email', 'cart__user__full_name']
    readonly_fields = ['added_at', 'updated_at', 'subtotal_display', 'savings_display']
    ordering = ['-added_at']
    
    fieldsets = (
        ('Item Information', {
            'fields': ('cart', 'product', 'quantity', 'price_at_addition')
        }),
        ('Pricing', {
            'fields': ('subtotal_display', 'savings_display')
        }),
        ('Timestamps', {
            'fields': ('added_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def cart_display(self, obj):
        return str(obj.cart)
    cart_display.short_description = 'Cart'
    
    def subtotal_display(self, obj):
        return f"EGP {obj.subtotal:.2f}"
    subtotal_display.short_description = 'Subtotal'
    
    def savings_display(self, obj):
        return f"EGP {obj.savings:.2f}" if obj.savings > 0 else "No savings"
    savings_display.short_description = 'Savings'
    
    def has_add_permission(self, request):
        # Disable manual cart item creation
        return False
