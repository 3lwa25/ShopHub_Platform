"""
Django Admin Configuration for Reviews App
"""
from django.contrib import admin
from .models import Review, ReviewImage, ReviewHelpful


class ReviewImageInline(admin.TabularInline):
    model = ReviewImage
    extra = 1
    fields = ['image', 'caption', 'display_order']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'buyer', 'rating', 'title', 'verified_purchase', 'helpful_count', 'status', 'created_at']
    list_filter = ['rating', 'verified_purchase', 'status', 'created_at']
    search_fields = ['product__title', 'buyer__email', 'title', 'body']
    readonly_fields = ['helpful_count', 'created_at', 'updated_at']
    inlines = [ReviewImageInline]
    ordering = ['-created_at']
    
    fieldsets = (
        ('Review Information', {
            'fields': ('product', 'buyer', 'order', 'rating', 'title', 'body')
        }),
        ('Status', {
            'fields': ('verified_purchase', 'status', 'helpful_count')
        }),
        ('Seller Response', {
            'fields': ('seller_response', 'seller_responded_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ReviewImage)
class ReviewImageAdmin(admin.ModelAdmin):
    list_display = ['review', 'caption', 'display_order', 'created_at']
    list_filter = ['created_at']
    search_fields = ['review__title', 'caption']


@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    list_display = ['review', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['review__title', 'user__email']

