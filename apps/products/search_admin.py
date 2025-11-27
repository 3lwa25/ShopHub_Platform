"""
Admin for Search and Browsing Models
"""
from django.contrib import admin
from django.utils.html import format_html
from .search_models import SearchQuery, BrowsingHistory, ProductComparison


class SearchQueryAdmin(admin.ModelAdmin):
    """Admin for search queries"""
    list_display = ['query', 'user_link', 'results_count', 'created_at']
    list_filter = ['created_at', 'results_count']
    search_fields = ['query', 'user__email', 'session_key']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Query Information', {
            'fields': ('query', 'user', 'session_key', 'results_count')
        }),
        ('Filters', {
            'fields': ('filters_applied',)
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
    
    def user_link(self, obj):
        """Link to user"""
        if obj.user:
            return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
        return obj.session_key or 'Anonymous'
    user_link.short_description = 'User'
    
    def has_add_permission(self, request):
        return False


class BrowsingHistoryAdmin(admin.ModelAdmin):
    """Admin for browsing history"""
    list_display = ['product_link', 'user_link', 'duration', 'viewed_at']
    list_filter = ['viewed_at']
    search_fields = ['product__title', 'user__email', 'session_key']
    readonly_fields = ['viewed_at']
    date_hierarchy = 'viewed_at'
    
    fieldsets = (
        ('View Information', {
            'fields': ('product', 'user', 'session_key')
        }),
        ('Details', {
            'fields': ('duration', 'referrer', 'viewed_at')
        }),
    )
    
    def user_link(self, obj):
        """Link to user"""
        if obj.user:
            return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
        return obj.session_key or 'Anonymous'
    user_link.short_description = 'User'
    
    def product_link(self, obj):
        """Link to product"""
        return format_html('<a href="/admin/products/product/{}/change/">{}</a>', obj.product.id, obj.product.title)
    product_link.short_description = 'Product'
    
    def has_add_permission(self, request):
        return False


class ProductComparisonAdmin(admin.ModelAdmin):
    """Admin for product comparisons"""
    list_display = ['id', 'user_link', 'product_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__email', 'session_key']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    filter_horizontal = ['products']
    
    def user_link(self, obj):
        """Link to user"""
        if obj.user:
            return format_html('<a href="/admin/accounts/user/{}/change/">{}</a>', obj.user.id, obj.user.email)
        return obj.session_key or 'Anonymous'
    user_link.short_description = 'User'
    
    def product_count(self, obj):
        """Number of products in comparison"""
        return obj.products.count()
    product_count.short_description = 'Products'


# Register models
admin.site.register(SearchQuery, SearchQueryAdmin)
admin.site.register(BrowsingHistory, BrowsingHistoryAdmin)
admin.site.register(ProductComparison, ProductComparisonAdmin)

