"""
Error Handling Module

Centralized error handling and custom exceptions
"""

from flask import jsonify
import logging
from functools import wraps
import traceback

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base API Exception"""
    status_code = 400
    
    def __init__(self, message, status_code=None, payload=None):
        super().__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload
    
    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        return rv


class ValidationError(APIError):
    """Raised when request validation fails"""
    status_code = 400


class AuthenticationError(APIError):
    """Raised when authentication fails"""
    status_code = 401


class AuthorizationError(APIError):
    """Raised when user lacks required permissions"""
    status_code = 403


class NotFoundError(APIError):
    """Raised when a resource is not found"""
    status_code = 404


class ConflictError(APIError):
    """Raised when there's a conflict with the current state"""
    status_code = 409


class ExternalServiceError(APIError):
    """Raised when an external service fails"""
    status_code = 503


def handle_api_error(error):
    """Handle APIError exceptions"""
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    
    # Log the error
    if error.status_code >= 500:
        logger.error(f"API Error: {error.message}", exc_info=True)
    else:
        logger.warning(f"API Error: {error.message}")
    
    return response


def handle_generic_error(error):
    """Handle unexpected errors"""
    from flask import current_app, jsonify
    
    logger.error(f"Unexpected error: {str(error)}", exc_info=True)
    
    # In production, don't expose internal error details
    if current_app.config.get('DEBUG'):
        return jsonify({
            'error': 'Internal server error',
            'message': str(error),
            'type': type(error).__name__
        }), 500
    else:
        return jsonify({'error': 'Internal server error'}), 500


def handle_validation_error(error):
    """Handle validation errors from libraries like marshmallow"""
    return jsonify({
        'error': 'Validation failed',
        'errors': error.messages
    }), 400


def register_error_handlers(app):
    """Register all error handlers with the Flask app"""
    app.register_error_handler(APIError, handle_api_error)
    app.register_error_handler(404, lambda e: handle_api_error(NotFoundError("Resource not found")))
    app.register_error_handler(500, handle_generic_error)
    
    # Handle other common exceptions
    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        return handle_generic_error(error)


def safe_execute(func):
    """Decorator to safely execute functions with error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except APIError:
            raise  # Re-raise API errors to be handled by error handlers
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
            raise APIError(f"Operation failed: {str(e)}", status_code=500)
    
    return wrapper


def validate_required_fields(data, required_fields):
    """Validate that required fields are present in data"""
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    
    if missing_fields:
        raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")
    
    return True


def validate_email(email):
    """Validate email format"""
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        raise ValidationError(f"Invalid email format: {email}")
    
    return True


def validate_url(url):
    """Validate URL format"""
    from urllib.parse import urlparse
    
    try:
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            raise ValidationError(f"Invalid URL format: {url}")
    except Exception:
        raise ValidationError(f"Invalid URL format: {url}")
    
    return True