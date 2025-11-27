from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('', views.notification_center, name='center'),
    path('mark-read/<int:notification_id>/', views.mark_as_read, name='mark_read'),
    path('mark-all-read/', views.mark_all_as_read, name='mark_all_read'),
    path('unread-count/', views.get_unread_count, name='unread_count'),
]

