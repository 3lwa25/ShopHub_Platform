"""
Django Admin Configuration for Analytics App
"""
from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'event_type', 'session_id', 'timestamp']
    list_filter = ['event_type', 'timestamp']
    search_fields = ['user__email', 'product__title', 'session_id']
    readonly_fields = ['timestamp']
    ordering = ['-timestamp']
    date_hierarchy = 'timestamp'

