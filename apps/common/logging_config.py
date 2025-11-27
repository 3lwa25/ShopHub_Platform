"""
Logging and Monitoring Configuration
"""
import logging
import os
from datetime import datetime
from django.conf import settings


# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(settings.BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)


# Logging configuration
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {process:d} {thread:d} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'simple': {
            'format': '[{levelname}] {asctime} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        }
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file_general': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'general.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'file_errors': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'errors.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'file_security': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'security.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'file_performance': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'performance.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'file_database': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'database.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
            'formatter': 'verbose'
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file_general'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['file_errors', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['file_security'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['file_database'],
            'level': 'WARNING',  # Set to DEBUG to log all queries
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file_general', 'file_errors'],
            'level': 'INFO',
            'propagate': False,
        },
        'performance': {
            'handlers': ['file_performance'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file_general'],
        'level': 'INFO',
    },
}


class PerformanceLogger:
    """
    Logger for performance monitoring
    """
    
    def __init__(self):
        self.logger = logging.getLogger('performance')
    
    def log_query_time(self, query, duration):
        """Log slow database queries"""
        if duration > 0.1:  # Log queries taking more than 100ms
            self.logger.warning(f'Slow query ({duration:.3f}s): {query}')
    
    def log_view_time(self, view_name, duration, status_code):
        """Log view response times"""
        if duration > 1.0:  # Log views taking more than 1 second
            self.logger.warning(
                f'Slow view: {view_name} - {duration:.3f}s - Status: {status_code}'
            )
        else:
            self.logger.info(
                f'View: {view_name} - {duration:.3f}s - Status: {status_code}'
            )
    
    def log_api_call(self, endpoint, duration, status_code):
        """Log API call performance"""
        self.logger.info(
            f'API: {endpoint} - {duration:.3f}s - Status: {status_code}'
        )


class SecurityLogger:
    """
    Logger for security events
    """
    
    def __init__(self):
        self.logger = logging.getLogger('django.security')
    
    def log_login_attempt(self, username, success, ip_address):
        """Log login attempts"""
        if success:
            self.logger.info(f'Successful login: {username} from {ip_address}')
        else:
            self.logger.warning(f'Failed login attempt: {username} from {ip_address}')
    
    def log_password_reset(self, username, ip_address):
        """Log password reset attempts"""
        self.logger.info(f'Password reset requested: {username} from {ip_address}')
    
    def log_suspicious_activity(self, description, user, ip_address):
        """Log suspicious activities"""
        self.logger.warning(
            f'Suspicious activity: {description} - User: {user} - IP: {ip_address}'
        )
    
    def log_permission_denied(self, user, resource, action):
        """Log permission denied events"""
        self.logger.warning(
            f'Permission denied: User {user} attempted {action} on {resource}'
        )


class ApplicationLogger:
    """
    General application logger
    """
    
    def __init__(self, name='apps'):
        self.logger = logging.getLogger(name)
    
    def info(self, message, **kwargs):
        """Log info message"""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message, **kwargs):
        """Log warning message"""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message, exc_info=None, **kwargs):
        """Log error message"""
        self.logger.error(message, exc_info=exc_info, extra=kwargs)
    
    def critical(self, message, exc_info=None, **kwargs):
        """Log critical message"""
        self.logger.critical(message, exc_info=exc_info, extra=kwargs)
    
    def debug(self, message, **kwargs):
        """Log debug message"""
        self.logger.debug(message, extra=kwargs)


# Create logger instances
performance_logger = PerformanceLogger()
security_logger = SecurityLogger()
app_logger = ApplicationLogger()


# Middleware for performance monitoring
class PerformanceMonitoringMiddleware:
    """
    Middleware to monitor view performance
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        import time
        start_time = time.time()
        
        response = self.get_response(request)
        
        duration = time.time() - start_time
        view_name = request.resolver_match.view_name if request.resolver_match else 'unknown'
        
        performance_logger.log_view_time(view_name, duration, response.status_code)
        
        return response


# Context processor for logging
def logging_context(request):
    """
    Add logging utilities to template context
    """
    return {
        'app_logger': app_logger,
    }

