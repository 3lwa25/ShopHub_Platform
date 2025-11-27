"""
Django Admin Configuration for Products App
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from apps.common.notifications import notify_product_status
from .models import Category, Product, ProductVariant, ProductImage

# Import search admin (models are auto-registered via @admin.register decorator)
try:
    from . import search_admin  # This will register the models
except ImportError:
    pass


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent', 'is_active', 'display_order', 'product_count']
    list_filter = ['is_active', 'parent', 'created_at']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    ordering = ['display_order', 'name']
    
    def product_count(self, obj):
        return obj.products.count()
    product_count.short_description = 'Products'


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'alt_text', 'is_primary', 'display_order']


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ['variant_sku', 'size', 'color', 'price_adjustment', 'stock']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'sku', 'seller', 'category', 'price', 'stock', 'status', 'rating', 'is_featured', 'vto_enabled']
    list_filter = ['status', 'is_featured', 'vto_enabled', 'category', 'created_at']
    search_fields = ['title', 'sku', 'description', 'category_path']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['rating', 'review_count', 'created_at', 'updated_at']
    inlines = [ProductImageInline, ProductVariantInline]
    ordering = ['-created_at']
    actions = ['make_active', 'make_inactive', 'make_featured', 'remove_featured', 'enable_vto', 'disable_vto']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('seller', 'title', 'slug', 'sku', 'description')
        }),
        ('Categorization', {
            'fields': ('category', 'category_path')
        }),
        ('Pricing', {
            'fields': ('price', 'compare_at_price', 'currency')
        }),
        ('Inventory', {
            'fields': ('stock', 'low_stock_threshold')
        }),
        ('Attributes', {
            'fields': ('attributes',),
            'classes': ('collapse',)
        }),
        ('Status & Features', {
            'fields': ('status', 'is_featured', 'vto_enabled')
        }),
        ('Ratings', {
            'fields': ('rating', 'review_count'),
            'classes': ('collapse',)
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def make_active(self, request, queryset):
        updated = 0
        for product in queryset.select_related('seller__user'):
            if product.status != 'active':
                product.status = 'active'
                product.save(update_fields=['status', 'updated_at'])
                notify_product_status(
                    product,
                    is_active=True,
                    is_featured=product.is_featured,
                    reason=_('Your product has been approved and published in the storefront.')
                )
                updated += 1
        self.message_user(request, f'{updated} products marked as active.')
    make_active.short_description = 'Mark selected products as active'
    
    def make_inactive(self, request, queryset):
        updated = 0
        for product in queryset.select_related('seller__user'):
            if product.status != 'inactive':
                product.status = 'inactive'
                product.save(update_fields=['status', 'updated_at'])
                notify_product_status(
                    product,
                    is_active=False,
                    is_featured=product.is_featured,
                    reason=_('Your product has been deactivated by an administrator. Please review the listing and contact support if needed.')
                )
                updated += 1
        self.message_user(request, f'{updated} products marked as inactive.')
    make_inactive.short_description = 'Mark selected products as inactive'
    
    def make_featured(self, request, queryset):
        updated = 0
        for product in queryset.select_related('seller__user'):
            if not product.is_featured:
                product.is_featured = True
                product.save(update_fields=['is_featured', 'updated_at'])
                notify_product_status(
                    product,
                    is_active=(product.status == 'active'),
                    is_featured=True,
                    reason=_('Great news! Your product has been highlighted as a featured item.')
                )
                updated += 1
        self.message_user(request, f'{updated} products marked as featured.')
    make_featured.short_description = 'Mark selected products as featured'
    
    def remove_featured(self, request, queryset):
        updated = 0
        for product in queryset.select_related('seller__user'):
            if product.is_featured:
                product.is_featured = False
                product.save(update_fields=['is_featured', 'updated_at'])
                notify_product_status(
                    product,
                    is_active=(product.status == 'active'),
                    is_featured=False,
                    reason=_('Your product is no longer featured. Continue delivering great experiences to regain the spotlight!')
                )
                updated += 1
        self.message_user(request, f'{updated} products removed from featured.')
    remove_featured.short_description = 'Remove selected products from featured'
    
    def enable_vto(self, request, queryset):
        updated = queryset.update(vto_enabled=True)
        self.message_user(request, f'Virtual Try-On enabled for {updated} products.')
    enable_vto.short_description = 'Enable Virtual Try-On'
    
    def disable_vto(self, request, queryset):
        updated = queryset.update(vto_enabled=False)
        self.message_user(request, f'Virtual Try-On disabled for {updated} products.')
    disable_vto.short_description = 'Disable Virtual Try-On'


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'image_preview', 'is_primary', 'display_order']
    list_filter = ['is_primary', 'created_at']
    search_fields = ['product__title', 'alt_text']
    ordering = ['product', 'display_order']
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" />', obj.image.url)
        return '-'
    image_preview.short_description = 'Preview'


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['product', 'variant_sku', 'size', 'color', 'final_price', 'stock']
    list_filter = ['product', 'created_at']
    search_fields = ['variant_sku', 'product__title', 'size', 'color']
    ordering = ['product', 'size', 'color']

