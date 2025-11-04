"""
Django Admin Configuration for Virtual Try-On App
"""
from django.contrib import admin
from .models import VTOAsset, TryonSession, TryonImage


@admin.register(VTOAsset)
class VTOAssetAdmin(admin.ModelAdmin):
    list_display = ['product', 'asset_type', 'is_active', 'created_at']
    list_filter = ['asset_type', 'is_active', 'created_at']
    search_fields = ['product__title', 'product__sku']
    ordering = ['-created_at']


class TryonImageInline(admin.TabularInline):
    model = TryonImage
    extra = 0
    readonly_fields = ['status', 'created_at']
    fields = ['product', 'user_photo', 'result_image', 'status']


@admin.register(TryonSession)
class TryonSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'is_active', 'image_count', 'created_at', 'ended_at']
    list_filter = ['created_at', 'ended_at']
    search_fields = ['session_id', 'user__email']
    readonly_fields = ['session_id', 'created_at', 'ended_at']
    inlines = [TryonImageInline]
    ordering = ['-created_at']
    
    def image_count(self, obj):
        return obj.images.count()
    image_count.short_description = 'Images'


@admin.register(TryonImage)
class TryonImageAdmin(admin.ModelAdmin):
    list_display = ['session', 'product', 'status', 'auto_delete_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['session__session_id', 'product__title']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']

