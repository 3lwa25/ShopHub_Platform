"""
Django Admin Configuration for Wishlist App
"""
from django.contrib import admin
from .models import Wishlist, WishlistItem


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0
    fields = ['product', 'priority', 'notes', 'added_at']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'item_count', 'created_at', 'updated_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['user', 'created_at', 'updated_at']
    inlines = [WishlistItemInline]


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ['wishlist', 'product', 'priority', 'is_in_stock', 'added_at']
    list_filter = ['priority', 'added_at']
    search_fields = ['wishlist__user__email', 'product__title']

