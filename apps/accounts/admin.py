"""
Django Admin Configuration for Accounts App
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, SellerProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom admin interface for User model.
    """
    list_display = ['email', 'username', 'full_name', 'role', 'is_active', 'verified', 'created_at']
    list_filter = ['role', 'is_active', 'verified', 'is_staff', 'is_superuser', 'created_at']
    search_fields = ['email', 'username', 'full_name', 'phone']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        (_('Personal info'), {
            'fields': ('full_name', 'first_name', 'last_name', 'phone', 'avatar')
        }),
        (_('Permissions'), {
            'fields': ('role', 'is_active', 'verified', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'role', 'is_staff', 'is_superuser'),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_login', 'date_joined']


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for SellerProfile model.
    """
    list_display = ['user', 'business_name', 'verified_seller', 'total_sales', 'rating', 'total_orders', 'created_at']
    list_filter = ['verified_seller', 'created_at', 'country']
    search_fields = ['user__email', 'user__username', 'business_name', 'business_description']
    readonly_fields = ['user', 'total_sales', 'total_orders', 'rating', 'rating_count', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        (_('Seller Information'), {
            'fields': ('user', 'business_name', 'business_description', 'logo')
        }),
        (_('Business Address'), {
            'fields': ('address', 'city', 'country', 'postal_code')
        }),
        (_('Verification & Status'), {
            'fields': ('verified_seller', 'total_sales', 'total_orders', 'rating', 'rating_count')
        }),
        (_('Social Media'), {
            'fields': ('website', 'facebook', 'instagram'),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make user field read-only after creation"""
        if obj:  # editing an existing object
            return self.readonly_fields + ['user']
        return self.readonly_fields

