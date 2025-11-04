"""
Django Admin Configuration for Orders App
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Cart, CartItem, Order, OrderItem, ShipmentTracking


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ['subtotal']
    fields = ['product', 'variant', 'quantity', 'subtotal']


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'total_items', 'total_price', 'updated_at']
    list_filter = ['created_at', 'updated_at']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['user', 'created_at', 'updated_at']
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'product', 'variant', 'quantity', 'unit_price', 'subtotal']
    list_filter = ['added_at']
    search_fields = ['cart__user__email', 'product__title']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['subtotal']
    fields = ['product', 'variant', 'product_name', 'quantity', 'unit_price', 'subtotal', 'status']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'buyer', 'total_amount', 'status', 'payment_status', 'created_at']
    list_filter = ['status', 'payment_status', 'created_at', 'currency']
    search_fields = ['order_number', 'buyer__email', 'buyer__username']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'buyer', 'total_amount', 'currency', 'status')
        }),
        ('Payment', {
            'fields': ('payment_method', 'payment_status', 'reward_points_used', 'points_earned')
        }),
        ('Shipping', {
            'fields': ('shipping_address',)
        }),
        ('Notes', {
            'fields': ('customer_notes', 'admin_notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product_name', 'quantity', 'unit_price', 'subtotal', 'status']
    list_filter = ['status', 'created_at']
    search_fields = ['order__order_number', 'product_name', 'product_sku']


@admin.register(ShipmentTracking)
class ShipmentTrackingAdmin(admin.ModelAdmin):
    list_display = ['order', 'courier_name', 'tracking_number', 'current_status', 'estimated_delivery', 'created_at']
    list_filter = ['current_status', 'courier_name', 'created_at']
    search_fields = ['order__order_number', 'tracking_number', 'courier_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

