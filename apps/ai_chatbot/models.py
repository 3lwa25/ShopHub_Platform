"""
AI Chatbot Models for Shop Hub
Powered by Google Gemini AI
"""
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
import uuid
from decimal import Decimal

from apps.products.models import Product


class ChatSession(models.Model):
    """
    Chat session for AI chatbot conversations.
    Tracks conversation history for context.
    """
    # User (nullable for guests)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_sessions',
        db_index=True
    )
    
    # Session identifier
    session_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        default=uuid.uuid4,
        help_text=_('Unique session identifier')
    )
    
    # Session title/summary
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text=_('Chat session title (auto-generated from first message)')
    )
    
    # Session metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Session metadata (user preferences, context, etc.)')
    )
    
    # Session status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text=_('Is session active?')
    )
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chat_sessions'
        verbose_name = _('Chat Session')
        verbose_name_plural = _('Chat Sessions')
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', '-last_activity']),
            models.Index(fields=['session_id']),
            models.Index(fields=['is_active', '-last_activity']),
        ]
    
    def __str__(self):
        user_str = self.user.email if self.user else 'Guest'
        return f"Chat {self.session_id[:8]} - {user_str}"
    
    def end_session(self):
        """Mark session as ended"""
        from django.utils import timezone
        if self.is_active:
            self.is_active = False
            self.ended_at = timezone.now()
            self.save(update_fields=['is_active', 'ended_at'])
    
    @property
    def message_count(self):
        """Total number of messages in this session"""
        return self.messages.count()
    
    def get_context_messages(self, limit=10):
        """
        Get recent messages for AI context.
        
        Args:
            limit (int): Maximum number of messages to return
        
        Returns:
            QuerySet: Recent chat messages
        """
        return self.messages.order_by('-created_at')[:limit][::-1]  # Oldest first
    
    def generate_title(self):
        """
        Auto-generate session title from first user message.
        """
        first_message = self.messages.filter(role='user').first()
        if first_message and not self.title:
            # Truncate message to 50 characters
            self.title = first_message.content[:50]
            if len(first_message.content) > 50:
                self.title += '...'
            self.save(update_fields=['title'])


class ChatMessage(models.Model):
    """
    Individual messages in a chat session.
    Stores both user and AI bot messages.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'AI Assistant'),
        ('system', 'System'),
    ]
    
    # Session relationship
    session = models.ForeignKey(
        ChatSession,
        on_delete=models.CASCADE,
        related_name='messages',
        db_index=True
    )
    
    # Message sender role
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        db_index=True,
        help_text=_('Who sent this message')
    )
    
    # Message content
    content = models.TextField(
        help_text=_('Message text content')
    )
    
    # Additional metadata (e.g., product references, links, etc.)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text=_('Additional message data (product IDs, links, etc.)')
    )
    
    # AI model information (for assistant messages)
    model = models.CharField(
        max_length=50,
        blank=True,
        help_text=_('AI model used (e.g., gemini-2.5-flash)')
    )
    
    # Token usage (for cost tracking)
    tokens_used = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_('Number of tokens used for this message')
    )
    
    # Response time (for assistant messages)
    response_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_('AI response time in milliseconds')
    )
    
    # Feedback
    helpful = models.BooleanField(
        null=True,
        blank=True,
        help_text=_('Was this message helpful? (user feedback)')
    )
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'chat_messages'
        verbose_name = _('Chat Message')
        verbose_name_plural = _('Chat Messages')
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['role']),
        ]
    
    def __str__(self):
        preview = self.content[:50]
        if len(self.content) > 50:
            preview += '...'
        return f"{self.get_role_display()}: {preview}"
    
    @property
    def is_user_message(self):
        """Check if this is a user message"""
        return self.role == 'user'
    
    @property
    def is_assistant_message(self):
        """Check if this is an AI assistant message"""
        return self.role == 'assistant'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        
        # Auto-generate session title from first user message
        if self.role == 'user' and self.session.message_count == 1:
            self.session.generate_title()


class ChatFeedback(models.Model):
    """
    Detailed feedback on AI responses.
    Used for improving chatbot performance.
    """
    # Message relationship
    message = models.OneToOneField(
        ChatMessage,
        on_delete=models.CASCADE,
        related_name='feedback',
        primary_key=True
    )
    
    # Feedback type
    feedback_type = models.CharField(
        max_length=20,
        choices=[
            ('helpful', 'Helpful'),
            ('not_helpful', 'Not Helpful'),
            ('incorrect', 'Incorrect Information'),
            ('inappropriate', 'Inappropriate'),
            ('other', 'Other'),
        ]
    )
    
    # Detailed feedback text
    comment = models.TextField(
        blank=True,
        help_text=_('Detailed feedback from user')
    )
    
    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_feedback'
        verbose_name = _('Chat Feedback')
        verbose_name_plural = _('Chat Feedback')
    
    def __str__(self):
        return f"Feedback for message {self.message.id} - {self.feedback_type}"


class ProductKnowledge(models.Model):
    """
    Lightweight search index for product/domain knowledge used by the AI chatbot.
    Populated via management command from curated datasets (meta + reviews).
    """

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='knowledge_entries',
        help_text=_('Optional link to an internal catalog product'),
    )
    external_id = models.CharField(
        max_length=100,
        unique=True,
        help_text=_('External identifier (e.g., ASIN) used in the dataset'),
    )
    title = models.CharField(max_length=255, db_index=True)
    category = models.CharField(max_length=255, blank=True, db_index=True)
    description = models.TextField(blank=True)
    highlights = models.JSONField(default=list, blank=True, help_text=_('Key bullet points/features'))
    review_snippets = models.JSONField(default=list, blank=True, help_text=_('Short review quotes'))
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Average rating from dataset (0-5)'),
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Price information if available'),
    )
    source = models.CharField(max_length=255, blank=True, help_text=_('Dataset file this record came from'))
    metadata = models.JSONField(default=dict, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'chatbot_product_knowledge'
        verbose_name = _('Product Knowledge Entry')
        verbose_name_plural = _('Product Knowledge Entries')
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['title']),
        ]

    def __str__(self):
        return self.title[:80]

