"""
Admin for Coupon Models
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .coupon_models import Coupon, CouponUsage


class CouponAdmin(admin.ModelAdmin):
    """Admin for coupons"""
    list_display = ['code', 'discount_display', 'usage_display', 'validity_status', 'is_active', 'created_at']
    list_filter = ['discount_type', 'is_active', 'first_order_only', 'created_at', 'valid_from', 'valid_to']
    search_fields = ['code', 'description']
    readonly_fields = ['current_uses', 'created_at', 'updated_at']
    filter_horizontal = ['applicable_categories', 'applicable_products', 'allowed_users']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Coupon Information', {
            'fields': ('code', 'description', 'is_active')
        }),
        ('Discount Details', {
            'fields': ('discount_type', 'discount_value', 'max_discount_amount')
        }),
        ('Conditions', {
            'fields': ('min_order_value', 'applicable_categories', 'applicable_products')
        }),
        ('Usage Limits', {
            'fields': ('max_uses', 'max_uses_per_user', 'current_uses')
        }),
        ('Validity Period', {
            'fields': ('valid_from', 'valid_to')
        }),
        ('User Restrictions', {
            'fields': ('first_order_only', 'allowed_users'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['activate_coupons', 'deactivate_coupons', 'reset_usage']
    
    def discount_display(self, obj):
        """Display discount in human-readable format"""
        return obj.get_discount_display()
    discount_display.short_description = 'Discount'
    
    def usage_display(self, obj):
        """Display usage statistics"""
        if obj.max_uses:
            percentage = (obj.current_uses / obj.max_uses) * 100
            color = 'green' if percentage < 70 else 'orange' if percentage < 90 else 'red'
            return format_html(
                '<span style="color: {};">{} / {} ({}%)</span>',
                color, obj.current_uses, obj.max_uses, int(percentage)
            )
        return f"{obj.current_uses} / ∞"
    usage_display.short_description = 'Usage'
    
    def validity_status(self, obj):
        """Display validity status"""
        now = timezone.now()
        if now < obj.valid_from:
            return format_html('<span style="color: orange;">⏳ Not Yet Valid</span>')
        elif now > obj.valid_to:
            return format_html('<span style="color: red;">⏰ Expired</span>')
        else:
            return format_html('<span style="color: green;">✓ Valid</span>')
    validity_status.short_description = 'Validity'
    
    def activate_coupons(self, request, queryset):
        """Activate selected coupons"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} coupon(s) activated.')
    activate_coupons.short_description = 'Activate selected coupons'
    
    def deactivate_coupons(self, request, queryset):
        """Deactivate selected coupons"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} coupon(s) deactivated.')
    deactivate_coupons.short_description = 'Deactivate selected coupons'
    
    def reset_usage(self, request, queryset):
        """Reset usage counter"""
        count = queryset.update(current_uses=0)
        self.message_user(request, f'Usage counter reset for {count} coupon(s).')
    reset_usage.short_description = 'Reset usage counter'
    
    def save_model(self, request, obj, form, change):
        """Set created_by if new"""
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class CouponUsageAdmin(admin.ModelAdmin):
    """Admin for coupon usage tracking"""
    list_display = ['coupon_link', 'user_link', 'order_link', 'discount_amount', 'used_at']
    list_filter = ['used_at']
    search_fields = ['coupon__code', 'user__email', 'order__order_number']
    readonly_fields = ['used_at']
    date_hierarchy = 'used_at'
    
    fieldsets = (
        ('Usage Information', {
            'fields': ('coupon', 'user', 'order')
        }),
        ('Details', {
            'fields': ('discount_amount', 'used_at')
        }),
    )
    
    def coupon_link(self, obj):
        """Link to coupon"""
        return format_html('<a href="/admin/orders/coupon/{}/change/">{}</a>', obj.coupon.id, obj.coupon.code)
    coupon_link.short_description = 'Coupon'
    
    def user_link(self, obj):
        """Link to user"""
        return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
    user_link.short_description = 'User'
    
    def order_link(self, obj):
        """Link to order"""
        return format_html('<a href="/admin/orders/order/{}/change/">{}</a>', obj.order.id, obj.order.order_number)
    order_link.short_description = 'Order'
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# Register models
admin.site.register(Coupon, CouponAdmin)
admin.site.register(CouponUsage, CouponUsageAdmin)

