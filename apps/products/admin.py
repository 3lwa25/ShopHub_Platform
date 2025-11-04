"""
Django Admin Configuration for Products App
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Product, ProductVariant, ProductImage


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

