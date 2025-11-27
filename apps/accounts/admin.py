"""
Django Admin Configuration for Accounts App
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, SellerProfile
from apps.common.notifications import notify_seller_status


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
    list_display = ['user', 'business_name', 'is_approved', 'is_verified', 'total_sales', 'rating', 'total_orders', 'created_at']
    list_filter = ['is_approved', 'is_verified', 'created_at']
    search_fields = ['user__email', 'user__username', 'business_name', 'business_address']
    readonly_fields = ['user', 'total_sales', 'total_orders', 'rating', 'created_at', 'updated_at', 'approval_date']
    ordering = ['-created_at']
    actions = ['approve_sellers', 'reject_sellers', 'verify_sellers', 'unverify_sellers']
    
    fieldsets = (
        (_('Seller Information'), {
            'fields': ('user', 'business_name', 'business_registration_number')
        }),
        (_('Business Contact'), {
            'fields': ('business_email', 'business_phone', 'business_address')
        }),
        (_('Verification & Status'), {
            'fields': ('is_approved', 'is_verified', 'approval_date', 'total_sales', 'total_orders', 'rating')
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
    
    def approve_sellers(self, request, queryset):
        """Bulk action to approve selected sellers"""
        updated = 0
        for seller_profile in queryset.select_related('user'):
            if not seller_profile.is_approved:
                seller_profile.is_approved = True
                seller_profile.save(update_fields=['is_approved', 'updated_at'])
                notify_seller_status(
                    seller_profile.user,
                    is_approved=True,
                    is_verified=seller_profile.is_verified,
                    reason=_('Your seller profile has been approved.')
                )
                updated += 1
        self.message_user(request, _(f'{updated} seller(s) have been approved.'))
    approve_sellers.short_description = _('Approve selected sellers')
    
    def reject_sellers(self, request, queryset):
        """Bulk action to reject/unapprove selected sellers"""
        updated = 0
        for seller_profile in queryset.select_related('user'):
            if seller_profile.is_approved:
                seller_profile.is_approved = False
                seller_profile.save(update_fields=['is_approved', 'updated_at'])
                notify_seller_status(
                    seller_profile.user,
                    is_approved=False,
                    is_verified=seller_profile.is_verified,
                    reason=_('Your seller profile has been rejected or temporarily disabled by an administrator.')
                )
                updated += 1
        self.message_user(request, _(f'{updated} seller(s) have been rejected/unapproved.'))
    reject_sellers.short_description = _('Reject/Unapprove selected sellers')
    
    def verify_sellers(self, request, queryset):
        """Bulk action to verify selected sellers (give verification badge)"""
        updated = 0
        for seller_profile in queryset.select_related('user'):
            if not seller_profile.is_verified:
                seller_profile.is_verified = True
                seller_profile.save(update_fields=['is_verified', 'updated_at'])
                notify_seller_status(
                    seller_profile.user,
                    is_approved=seller_profile.is_approved,
                    is_verified=True,
                    reason=_('Congratulations! Your store has earned the verified seller badge.')
                )
                updated += 1
        self.message_user(request, _(f'{updated} seller(s) have been verified.'))
    verify_sellers.short_description = _('Verify selected sellers (badge)')
    
    def unverify_sellers(self, request, queryset):
        """Bulk action to remove verification badge"""
        updated = 0
        for seller_profile in queryset.select_related('user'):
            if seller_profile.is_verified:
                seller_profile.is_verified = False
                seller_profile.save(update_fields=['is_verified', 'updated_at'])
                notify_seller_status(
                    seller_profile.user,
                    is_approved=seller_profile.is_approved,
                    is_verified=False,
                    reason=_('Your verified seller badge has been removed. Please contact support for details.')
                )
                updated += 1
        self.message_user(request, _(f'{updated} seller(s) verification removed.'))
    unverify_sellers.short_description = _('Remove verification badge')

