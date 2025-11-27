from django.urls import path

from . import views

app_name = 'ai_chatbot'

urlpatterns = [
    path('', views.chat_home, name='chat_home'),
    path('api/start/', views.api_start_session, name='api_start'),
    path('api/sessions/', views.api_sessions, name='api_sessions'),
    path('api/history/<str:session_id>/', views.api_session_history, name='api_history'),
    path('api/send/', views.api_send_message, name='api_send'),
    path('api/feedback/<int:message_id>/', views.api_feedback, name='api_feedback'),
]

