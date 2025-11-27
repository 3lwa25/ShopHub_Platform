"""
Django Admin Configuration for AI Chatbot App
"""
from django.contrib import admin
from .models import ChatSession, ChatMessage, ChatFeedback, ProductKnowledge


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ['created_at']
    fields = ['role', 'content', 'tokens_used', 'created_at']


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'title', 'is_active', 'message_count', 'started_at', 'last_activity']
    list_filter = ['is_active', 'started_at']
    search_fields = ['session_id', 'user__email', 'title']
    readonly_fields = ['session_id', 'started_at', 'ended_at', 'last_activity']
    inlines = [ChatMessageInline]
    ordering = ['-last_activity']
    
    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = 'Messages'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'role', 'content_preview', 'tokens_used', 'response_time_ms', 'created_at']
    list_filter = ['role', 'created_at']
    search_fields = ['session__session_id', 'content']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'


@admin.register(ChatFeedback)
class ChatFeedbackAdmin(admin.ModelAdmin):
    list_display = ['message', 'feedback_type', 'created_at']
    list_filter = ['feedback_type', 'created_at']
    search_fields = ['message__content', 'comment']


@admin.register(ProductKnowledge)
class ProductKnowledgeAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'average_rating', 'last_updated', 'source']
    search_fields = ['title', 'category', 'description', 'external_id']
    list_filter = ['category', 'source']
    readonly_fields = ['last_updated']
    ordering = ['-last_updated']

