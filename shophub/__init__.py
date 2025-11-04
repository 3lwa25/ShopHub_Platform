"""
Shop Hub - AI-Powered E-Commerce Platform
"""

__version__ = '1.0.0'
__author__ = 'Shop Hub Team'

# Celery is optional - only import if installed
try:
    from .celery import app as celery_app
    __all__ = ('celery_app',)
except ImportError:
    # Celery not installed, continue without it
    celery_app = None
    __all__ = ()

