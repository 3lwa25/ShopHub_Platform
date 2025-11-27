"""
AI Chatbot Views with Enhanced Error Handling and User Experience
"""
from __future__ import annotations

import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseServerError
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from .models import ChatSession, ChatMessage, ChatFeedback
from .services import GeminiChatService, ChatbotError, APIKeyError, APIConnectionError, APIQuotaError

logger = logging.getLogger(__name__)


def chat_home(request):
    """
    Render the chatbot dashboard with proper context.
    """
    context = {
        'page_title': 'AI Shopping Assistant',
        'page_description': 'Get personalized product recommendations and shopping assistance',
    }
    return render(request, 'ai_chatbot/chat.html', context)


def _get_or_create_session(request, session_id: str | None = None) -> ChatSession:
    """
    Get existing session or create a new one.
    
    Args:
        request: Django request object
        session_id: Optional session ID to retrieve
        
    Returns:
        ChatSession object
        
    Raises:
        PermissionError: If user doesn't own the session
    """
    qs = ChatSession.objects.all()

    if session_id:
        session = qs.filter(session_id=session_id).first()
        if session:
            # Verify session ownership
            if session.user and request.user.is_authenticated and session.user != request.user:
                logger.warning(
                    f'User {request.user.email} attempted to access session {session_id} '
                    f'owned by {session.user.email}'
                )
                raise PermissionError("You do not have permission to access this session.")
            return session

    # Create new session
    session = ChatSession.objects.create(
        user=request.user if request.user.is_authenticated else None
    )
    
    # Track session in Django session for guest users
    session_ids = request.session.get('chat_session_ids', [])
    session_ids.append(str(session.session_id))
    request.session['chat_session_ids'] = session_ids
    
    logger.info(f'Created new chat session: {session.session_id}')
    return session


@require_POST
def api_start_session(request):
    """
    API endpoint to start a new chat session.
    
    Returns:
        JSON response with session details
    """
    try:
        session = _get_or_create_session(request, session_id=None)
        return JsonResponse({
            'success': True,
            'session_id': session.session_id,
            'title': session.title or 'New conversation',
            'started_at': session.started_at.isoformat(),
        })
    except Exception as e:
        logger.error(f'Error starting session: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to start chat session. Please try again.'
        }, status=500)


@require_GET
def api_session_history(request, session_id: str):
    """
    API endpoint to retrieve chat history for a session.
    
    Args:
        session_id: Session ID to retrieve
        
    Returns:
        JSON response with message history
    """
    try:
        session = get_object_or_404(ChatSession, session_id=session_id)
        
        # Verify session ownership
        if session.user and request.user.is_authenticated and session.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to access this session.'
            }, status=403)

        messages_payload = [
            {
                'id': message.id,
                'role': message.role,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
                'metadata': message.metadata,
            }
            for message in session.messages.order_by('created_at')
        ]
        
        return JsonResponse({
            'success': True,
            'session_id': session.session_id,
            'title': session.title or 'Conversation',
            'messages': messages_payload
        })
    
    except ChatSession.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Chat session not found.'
        }, status=404)
    
    except Exception as e:
        logger.error(f'Error retrieving session history: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to load chat history. Please try again.'
        }, status=500)


@require_POST
def api_send_message(request):
    """
    API endpoint to send a message and get AI response.
    
    Expects JSON payload:
        {
            "message": "User message text",
            "session_id": "optional-session-id"
        }
    
    Returns:
        JSON response with user message and AI response
    """
    try:
        # Parse request payload
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON format in request.'
            }, status=400)

        message_text = (payload.get('message') or '').strip()
        session_id = payload.get('session_id')

        # Validate message
        if not message_text:
            return JsonResponse({
                'success': False,
                'error': 'Message cannot be empty.'
            }, status=400)
        
        if len(message_text) > 5000:
            return JsonResponse({
                'success': False,
                'error': 'Message is too long. Please keep it under 5000 characters.'
            }, status=400)

        # Get or create session
        try:
            session = _get_or_create_session(request, session_id=session_id)
        except PermissionError as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=403)

        # Save user message
        user_message = ChatMessage.objects.create(
            session=session,
            role='user',
            content=message_text,
        )
        logger.info(f'User message saved: {user_message.id}')

        # Get AI response
        try:
            service = GeminiChatService()
            response_payload = service.send(session, message_text)
            
            # Save assistant message
            assistant_message = ChatMessage.objects.create(
                session=session,
                role='assistant',
                content=response_payload['text'],
                model=response_payload['metadata'].get('model'),
                response_time_ms=response_payload['metadata'].get('response_time_ms'),
                metadata=response_payload['metadata'],
            )
            logger.info(f'Assistant message saved: {assistant_message.id}')
            
            return JsonResponse({
                'success': True,
                'session_id': session.session_id,
                'user_message': {
                    'id': user_message.id,
                    'role': user_message.role,
                    'content': user_message.content,
                    'created_at': user_message.created_at.isoformat(),
                },
                'assistant_message': {
                    'id': assistant_message.id,
                    'role': assistant_message.role,
                    'content': assistant_message.content,
                    'created_at': assistant_message.created_at.isoformat(),
                    'metadata': response_payload['metadata'],
                },
            })
        
        except APIKeyError as e:
            logger.error(f'API Key Error: {str(e)}')
            return JsonResponse({
                'success': False,
                'error': 'AI service is not properly configured. Please contact support.',
                'error_type': 'api_key_error'
            }, status=503)
        
        except APIQuotaError as e:
            logger.error(f'API Quota Error: {str(e)}')
            return JsonResponse({
                'success': False,
                'error': 'AI service quota exceeded. Please try again later.',
                'error_type': 'quota_exceeded'
            }, status=503)
        
        except APIConnectionError as e:
            logger.error(f'API Connection Error: {str(e)}')
            return JsonResponse({
                'success': False,
                'error': 'Unable to connect to AI service. Please check your internet connection and try again.',
                'error_type': 'connection_error'
            }, status=503)
        
        except ChatbotError as e:
            logger.error(f'Chatbot Error: {str(e)}')
            return JsonResponse({
                'success': False,
                'error': str(e),
                'error_type': 'chatbot_error'
            }, status=500)
    
    except Exception as e:
        logger.error(f'Unexpected error in api_send_message: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred. Please try again or contact support.',
            'error_type': 'unexpected_error'
        }, status=500)


@require_POST
def api_feedback(request, message_id: int):
    """
    API endpoint to submit feedback on a message.
    
    Args:
        message_id: ID of the message to provide feedback for
        
    Expects JSON payload:
        {
            "feedback_type": "helpful|not_helpful|incorrect|inappropriate|other",
            "comment": "Optional detailed feedback"
        }
    
    Returns:
        JSON response confirming feedback submission
    """
    try:
        message = get_object_or_404(ChatMessage, id=message_id)
        
        # Verify session ownership
        if message.session.user and request.user.is_authenticated and message.session.user != request.user:
            return JsonResponse({
                'success': False,
                'error': 'You do not have permission to provide feedback on this message.'
            }, status=403)

        try:
            payload = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON format in request.'
            }, status=400)

        feedback_type = payload.get('feedback_type')
        comment = payload.get('comment', '')

        if not feedback_type:
            return JsonResponse({
                'success': False,
                'error': 'feedback_type is required.'
            }, status=400)
        
        valid_types = ['helpful', 'not_helpful', 'incorrect', 'inappropriate', 'other']
        if feedback_type not in valid_types:
            return JsonResponse({
                'success': False,
                'error': f'Invalid feedback_type. Must be one of: {", ".join(valid_types)}'
            }, status=400)

        # Save feedback
        ChatFeedback.objects.update_or_create(
            message=message,
            defaults={'feedback_type': feedback_type, 'comment': comment},
        )
        
        # Update message helpful field
        message.helpful = feedback_type == 'helpful'
        message.save(update_fields=['helpful'])
        
        logger.info(f'Feedback submitted for message {message_id}: {feedback_type}')

        return JsonResponse({
            'success': True,
            'message': 'Thank you for your feedback!'
        })
    
    except ChatMessage.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Message not found.'
        }, status=404)
    
    except Exception as e:
        logger.error(f'Error submitting feedback: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to submit feedback. Please try again.'
        }, status=500)


@require_GET
def api_sessions(request):
    """
    API endpoint to retrieve list of user's chat sessions.
    
    Returns:
        JSON response with list of sessions
    """
    try:
        if request.user.is_authenticated:
            qs = ChatSession.objects.filter(user=request.user)
        else:
            # Get sessions for guest users
            session_ids = request.session.get('chat_session_ids', [])
            qs = ChatSession.objects.filter(session_id__in=session_ids)

        data = [
            {
                'session_id': session.session_id,
                'title': session.title or 'New conversation',
                'started_at': session.started_at.isoformat(),
                'last_activity': session.last_activity.isoformat(),
                'is_active': session.is_active,
                'message_count': session.message_count,
            }
            for session in qs.order_by('-last_activity')[:20]
        ]
        
        return JsonResponse({
            'success': True,
            'sessions': data
        })
    
    except Exception as e:
        logger.error(f'Error retrieving sessions: {str(e)}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to load chat sessions. Please try again.'
        }, status=500)
