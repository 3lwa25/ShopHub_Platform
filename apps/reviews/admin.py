"""
Admin configuration for Reviews
"""
from django.contrib import admin
from django.utils.html import format_html

from apps.notifications.models import Notification
from .models import Review, ReviewImage, ReviewHelpful


class ReviewImageInline(admin.TabularInline):
    """Inline admin for review images"""
    model = ReviewImage
    extra = 0
    fields = ('image', 'caption', 'display_order')
    readonly_fields = ('image',)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Admin for Product Reviews"""
    list_display = ['id', 'product_link', 'buyer_link', 'rating_display', 'title', 'status', 'verified_purchase', 'helpful_count', 'created_at']
    list_filter = ['status', 'rating', 'verified_purchase', 'created_at']
    search_fields = ['title', 'body', 'product__title', 'buyer__email', 'buyer__full_name']
    readonly_fields = ['created_at', 'updated_at', 'seller_responded_at', 'helpful_count']
    inlines = [ReviewImageInline]
    
    fieldsets = (
        ('Review Information', {
            'fields': ('product', 'buyer', 'order', 'order_item', 'rating', 'title', 'body')
        }),
        ('Verification', {
            'fields': ('verified_purchase',)
        }),
        ('Moderation', {
            'fields': ('status',)
        }),
        ('Engagement', {
            'fields': ('helpful_count',)
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
    
    actions = ['approve_reviews', 'reject_reviews']
    
    def product_link(self, obj):
        """Link to product"""
        return format_html('<a href="/admin/products/product/{}/change/">{}</a>', obj.product.id, obj.product.title)
    product_link.short_description = 'Product'
    
    def buyer_link(self, obj):
        """Link to buyer"""
        return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.buyer.id, obj.buyer.email)
    buyer_link.short_description = 'Buyer'
    
    def rating_display(self, obj):
        """Display rating as stars"""
        return format_html('{}★', obj.rating)
    rating_display.short_description = 'Rating'
    
    def approve_reviews(self, request, queryset):
        """Approve selected reviews and send notifications"""
        count = 0
        for review in queryset:
            if review.status != 'approved':
                review.status = 'approved'
                review.save(update_fields=['status', 'updated_at'])
                
                # Create notification for buyer
                Notification.objects.create(
                    user=review.buyer,
                    notification_type='system',
                    title='Review Approved',
                    message=f'Your review for "{review.product.title}" has been approved and is now visible.',
                    link=f'/products/{review.product.slug}/#reviews',
                )
                count += 1
        
        self.message_user(request, f'{count} review(s) approved. Buyers have been notified.')
    approve_reviews.short_description = 'Approve selected reviews'
    
    def reject_reviews(self, request, queryset):
        """Reject selected reviews and send notifications"""
        count = 0
        for review in queryset:
            if review.status != 'rejected':
                review.status = 'rejected'
                review.save(update_fields=['status', 'updated_at'])
                
                # Create notification for buyer
                Notification.objects.create(
                    user=review.buyer,
                    notification_type='system',
                    title='Review Rejected',
                    message=f'Your review for "{review.product.title}" has been rejected and will not be displayed.',
                    link='/reviews/my-reviews/',
                )
                count += 1
        
        self.message_user(request, f'{count} review(s) rejected. Buyers have been notified.')
    reject_reviews.short_description = 'Reject selected reviews'


@admin.register(ReviewImage)
class ReviewImageAdmin(admin.ModelAdmin):
    """Admin for Review Images"""
    list_display = ['id', 'review_link', 'image_preview', 'caption', 'display_order', 'created_at']
    list_filter = ['created_at']
    search_fields = ['review__title', 'caption']
    readonly_fields = ['created_at', 'image_preview']
    
    def review_link(self, obj):
        """Link to review"""
        return format_html('<a href="/admin/reviews/review/{}/change/">Review #{}</a>', obj.review.id, obj.review.id)
    review_link.short_description = 'Review'
    
    def image_preview(self, obj):
        """Show image preview"""
        if obj.image:
            return format_html('<img src="{}" style="max-width: 100px; max-height: 100px;" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Preview'


@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    """Admin for Helpful Votes"""
    list_display = ['id', 'review_link', 'user_link', 'created_at']
    list_filter = ['created_at']
    search_fields = ['review__title', 'user__email']
    readonly_fields = ['created_at']
    
    def review_link(self, obj):
        """Link to review"""
        return format_html('<a href="/admin/reviews/review/{}/change/">Review #{}</a>', obj.review.id, obj.review.id)
    review_link.short_description = 'Review'
    
    def user_link(self, obj):
        """Link to user"""
        return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
    user_link.short_description = 'User'
