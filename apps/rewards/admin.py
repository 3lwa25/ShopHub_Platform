"""
Django Admin Configuration for Rewards App
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    RewardAccount, PointsTransaction, Reward, RewardRedemption, 
    PointsGift, DailyLoginReward, Notification
)


@admin.register(RewardAccount)
class RewardAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'points_balance', 'total_earned', 'total_spent', 'tier', 'updated_at']
    list_filter = ['tier', 'updated_at']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['user', 'points_balance', 'total_earned', 'total_spent', 'created_at', 'updated_at']
    ordering = ['-points_balance']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Points Information', {
            'fields': ('points_balance', 'total_earned', 'total_spent')
        }),
        ('Tier Information', {
            'fields': ('tier',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'transaction_type', 'amount', 'balance_after', 'order', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['user__email', 'order__order_number', 'description']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'


@admin.register(Reward)
class RewardAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'reward_type', 'points_required', 'is_active', 
        'is_limited_time', 'redemption_count', 'tier_required', 'display_order'
    ]
    list_filter = ['reward_type', 'is_active', 'is_limited_time', 'tier_required']
    search_fields = ['name', 'description']
    ordering = ['display_order', 'points_required']
    list_editable = ['is_active', 'display_order']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'reward_type', 'icon')
        }),
        ('Points & Requirements', {
            'fields': ('points_required', 'tier_required')
        }),
        ('Reward Details', {
            'fields': ('discount_amount', 'free_product', 'charity_name'),
            'description': 'Fill in fields based on reward type'
        }),
        ('Availability', {
            'fields': ('is_active', 'is_limited_time', 'start_date', 'end_date')
        }),
        ('Limits', {
            'fields': ('max_redemptions', 'redemption_count', 'display_order')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['redemption_count', 'created_at', 'updated_at']
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # You can add custom save logic here


@admin.register(RewardRedemption)
class RewardRedemptionAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'reward', 'points_spent', 'status', 
        'coupon_code', 'created_at', 'processed_at'
    ]
    list_filter = ['status', 'created_at', 'processed_at']
    search_fields = ['user__email', 'reward__name', 'coupon_code']
    ordering = ['-created_at']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Redemption Information', {
            'fields': ('user', 'reward', 'points_spent', 'status')
        }),
        ('Generated Data', {
            'fields': ('coupon_code', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'processed_at', 'expires_at')
        }),
    )
    
    actions = ['mark_as_completed', 'mark_as_cancelled']
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f"{queryset.count()} redemptions marked as completed.")
    mark_as_completed.short_description = "Mark selected as completed"
    
    def mark_as_cancelled(self, request, queryset):
        queryset.update(status='cancelled')
        self.message_user(request, f"{queryset.count()} redemptions cancelled.")
    mark_as_cancelled.short_description = "Mark selected as cancelled"


@admin.register(PointsGift)
class PointsGiftAdmin(admin.ModelAdmin):
    list_display = ['sender', 'recipient', 'amount', 'status', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['sender__email', 'recipient__email']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'completed_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Gift Information', {
            'fields': ('sender', 'recipient', 'amount', 'message')
        }),
        ('Status', {
            'fields': ('status', 'created_at', 'completed_at')
        }),
    )
    
    actions = ['approve_gifts', 'reject_gifts']
    
    def approve_gifts(self, request, queryset):
        for gift in queryset.filter(status='pending'):
            if gift.process():
                self.message_user(request, f"Gift from {gift.sender.email} to {gift.recipient.email} approved.")
            else:
                self.message_user(request, f"Failed to process gift from {gift.sender.email}.", level='error')
    approve_gifts.short_description = "Approve selected gifts"
    
    def reject_gifts(self, request, queryset):
        queryset.update(status='rejected')
        self.message_user(request, f"{queryset.count()} gifts rejected.")
    reject_gifts.short_description = "Reject selected gifts"


@admin.register(DailyLoginReward)
class DailyLoginRewardAdmin(admin.ModelAdmin):
    list_display = ['user', 'login_date', 'points_earned', 'streak_day', 'created_at']
    list_filter = ['login_date', 'created_at']
    search_fields = ['user__email']
    ordering = ['-login_date']
    readonly_fields = ['created_at']
    date_hierarchy = 'login_date'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'notification_type', 'title', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at']
    search_fields = ['user__email', 'title', 'message']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'read_at']
    date_hierarchy = 'created_at'
    list_editable = ['is_read']
    
    fieldsets = (
        ('Notification Information', {
            'fields': ('user', 'notification_type', 'title', 'message', 'link')
        }),
        ('Status', {
            'fields': ('is_read', 'read_at')
        }),
        ('Additional Data', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        for notification in queryset.filter(is_read=False):
            notification.mark_as_read()
        self.message_user(request, f"{queryset.count()} notifications marked as read.")
    mark_as_read.short_description = "Mark selected as read"
    
    def mark_as_unread(self, request, queryset):
        queryset.update(is_read=False, read_at=None)
        self.message_user(request, f"{queryset.count()} notifications marked as unread.")
    mark_as_unread.short_description = "Mark selected as unread"

