"""
Virtual Try-On App Configuration
"""
from django.apps import AppConfig


class VirtualTryonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.virtual_tryon'
    verbose_name = 'Virtual Try-On'

