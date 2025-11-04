"""
Django Admin Configuration for Rewards App
"""
from django.contrib import admin
from .models import RewardAccount, PointsTransaction


@admin.register(RewardAccount)
class RewardAccountAdmin(admin.ModelAdmin):
    list_display = ['user', 'points_balance', 'total_earned', 'total_spent', 'tier', 'updated_at']
    list_filter = ['tier', 'updated_at']
    search_fields = ['user__email', 'user__username']
    readonly_fields = ['user', 'points_balance', 'total_earned', 'total_spent', 'created_at', 'updated_at']
    ordering = ['-points_balance']


@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'transaction_type', 'amount', 'balance_after', 'order', 'created_at']
    list_filter = ['transaction_type', 'created_at']
    search_fields = ['user__email', 'order__order_number', 'description']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

